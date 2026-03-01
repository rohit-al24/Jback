from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.models import Mondai
from core.transcription import TranscriptionError, transcribe_media


class Command(BaseCommand):
	help = "Transcribe a Mondai video (YouTube link or uploaded file) into Mondai.transcript using faster-whisper."

	def add_arguments(self, parser):
		parser.add_argument("public_id", type=str, help="Mondai public id (e.g. MON-ABC12345)")
		parser.add_argument(
			"--model",
			dest="model_size",
			default="large-v3",
			help="Whisper model size (default: large-v3).",
		)
		parser.add_argument(
			"--device",
			default="cuda",
			help="Device: cuda or cpu (default: cuda; auto-falls back if no CUDA).",
		)
		parser.add_argument(
			"--compute-type",
			dest="compute_type",
			default="float16",
			help="Compute type (e.g. float16, int8, int8_float16).",
		)
		parser.add_argument(
			"--language",
			default="ja",
			help="Language code (default: ja). Use 'auto' to auto-detect.",
		)
		parser.add_argument(
			"--beam-size",
			dest="beam_size",
			type=int,
			default=5,
			help="Beam size (default: 5).",
		)
		parser.add_argument(
			"--no-save",
			action="store_true",
			help="Do not store transcript in DB; just print it.",
		)

	def handle(self, *args, **options):
		public_id: str = options["public_id"]
		model_size: str = options["model_size"]
		device: str = options["device"]
		compute_type: str = options["compute_type"]
		language_opt: str = options["language"]
		beam_size: int = int(options["beam_size"])
		no_save: bool = bool(options["no_save"])

		mondai = Mondai.objects.filter(public_id=public_id).first()
		if not mondai:
			raise CommandError(f"Mondai not found: {public_id}")

		source: str | None = None
		if mondai.video_type == Mondai.VideoType.UPLOAD and mondai.video_file:
			source = mondai.video_file.path
		elif mondai.video_type in {Mondai.VideoType.LINK, Mondai.VideoType.EMBED}:
			source = mondai.video_url or mondai.video_embed_url

		if not source:
			raise CommandError(
				"Mondai has no transcribable source. Set video_type/upload or video_url first."
			)

		language = None if language_opt.strip().lower() == "auto" else language_opt.strip()

		self.stdout.write(self.style.NOTICE(f"Transcribing {public_id} from: {source}"))
		try:
			result = transcribe_media(
				source,
				model_size=model_size,
				device=device,
				compute_type=compute_type,
				language=language,
				beam_size=beam_size,
			)
		except TranscriptionError as e:
			raise CommandError(str(e)) from e

		lang = result.language or "unknown"
		prob = result.language_probability
		prob_str = f"{prob:.4f}" if isinstance(prob, float) else "n/a"

		self.stdout.write(self.style.SUCCESS(f"Detected language: {lang} (p={prob_str})"))
		self.stdout.write("\n--- TRANSCRIPT ---\n")
		self.stdout.write(result.text or "")
		self.stdout.write("\n--- SEGMENTS ---\n")
		for s in result.segments:
			start = float(s.get("start") or 0.0)
			end = float(s.get("end") or 0.0)
			text = (s.get("text") or "").strip()
			if not text:
				continue
			self.stdout.write(f"[{start:.2f}s -> {end:.2f}s] {text}")

		if no_save:
			return

		mondai.transcript = result.text
		mondai.save(update_fields=["transcript", "updated_at"])
		self.stdout.write(self.style.SUCCESS("Saved transcript to Mondai.transcript"))
