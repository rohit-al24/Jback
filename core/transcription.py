from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


class TranscriptionError(RuntimeError):
	pass


@dataclass(frozen=True)
class TranscriptionResult:
	language: str | None
	language_probability: float | None
	text: str
	segments: list[dict]


def _require_ffmpeg() -> str:
	ffmpeg_path = shutil.which("ffmpeg")
	if not ffmpeg_path and os.name == "nt":
		# If ffmpeg was installed after this process started (common on Windows),
		# the current PATH may be stale. Refresh from registry and retry.
		try:  # pragma: no cover
			import winreg

			def _read_reg_path(root, subkey: str) -> str:
				try:
					with winreg.OpenKey(root, subkey) as k:
						val, _ = winreg.QueryValueEx(k, "Path")
						return str(val or "")
				except Exception:
					return ""

			machine_path = _read_reg_path(
				winreg.HKEY_LOCAL_MACHINE,
				r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
			)
			user_path = _read_reg_path(winreg.HKEY_CURRENT_USER, r"Environment")
			if machine_path or user_path:
				os.environ["PATH"] = (machine_path + ";" + user_path).strip(";")
				ffmpeg_path = shutil.which("ffmpeg")
		except Exception:
			pass
	if not ffmpeg_path:
		raise TranscriptionError(
			"ffmpeg not found on PATH. Install ffmpeg and ensure `ffmpeg` is available. "
			"(faster-whisper uses ffmpeg to decode audio/video.)"
		)
	return ffmpeg_path


def _download_youtube_audio(url: str) -> str:
	"""Download best available audio for a YouTube URL to a temp file.

	Returns the full local filepath.
	"""
	try:
		from yt_dlp import YoutubeDL
	except Exception as e:  # pragma: no cover
		raise TranscriptionError(
			"yt-dlp is not installed. Install it or provide a local file path instead."
		) from e

	_require_ffmpeg()

	tmp_dir = Path(tempfile.mkdtemp(prefix="yt_audio_"))
	outtmpl = str(tmp_dir / "%(id)s.%(ext)s")

	ydl_opts = {
		"format": "bestaudio/best",
		"outtmpl": outtmpl,
		"noplaylist": True,
		"quiet": True,
		"no_warnings": True,
	}

	with YoutubeDL(ydl_opts) as ydl:
		info = ydl.extract_info(url, download=True)

	# yt-dlp may return a dict or list depending on playlist; we forced noplaylist.
	if not isinstance(info, dict) or "id" not in info:
		raise TranscriptionError("Could not download audio from URL")

	# Determine downloaded filename.
	video_id = info["id"]
	ext = info.get("ext")
	if ext:
		candidate = tmp_dir / f"{video_id}.{ext}"
		if candidate.exists():
			return str(candidate)

	# Fallback: search temp folder.
	files = list(tmp_dir.glob(f"{video_id}.*"))
	if not files:
		files = list(tmp_dir.glob("*"))
	if not files:
		raise TranscriptionError("Audio download produced no files")
	return str(files[0])


def transcribe_media(
	source: str,
	*,
	model_size: str = "large-v3",
	device: str = "cuda",
	compute_type: str = "float16",
	language: str | None = "ja",
	beam_size: int = 5,
	vad_filter: bool = True,
) -> TranscriptionResult:
	"""Transcribe an audio/video file or a YouTube URL using faster-whisper.

	- If `source` starts with http(s), it will be downloaded via yt-dlp.
	- Otherwise it is treated as a local file path.
	
	`language`: pass "ja" to bias to Japanese. Pass None to auto-detect.
	"""
	_require_ffmpeg()

	local_path = source
	if source.startswith("http://") or source.startswith("https://"):
		local_path = _download_youtube_audio(source)

	try:
		from faster_whisper import WhisperModel
		import ctranslate2
	except Exception as e:  # pragma: no cover
		raise TranscriptionError(
			"faster-whisper (and its runtime deps) are not installed or failed to import."
		) from e

	requested_device = (device or "").strip().lower()
	requested_compute = (compute_type or "").strip()
	
	# Graceful fallback if CUDA requested but unavailable.
	if requested_device == "cuda":
		try:
			if getattr(ctranslate2, "get_cuda_device_count")() <= 0:
				requested_device = "cpu"
				requested_compute = "int8"
		except Exception:
			# If we can't detect, keep the user's choice.
			pass

	model = WhisperModel(model_size, device=requested_device, compute_type=requested_compute)
	segments_iter, info = model.transcribe(
		local_path,
		beam_size=beam_size,
		language=language,
		vad_filter=vad_filter,
	)

	segments: list[dict] = []
	parts: list[str] = []
	for seg in segments_iter:
		text = (seg.text or "").strip()
		if text:
			parts.append(text)
		segments.append(
			{
				"start": float(seg.start),
				"end": float(seg.end),
				"text": seg.text,
			}
		)

	full_text = "\n".join(parts).strip()
	lang = getattr(info, "language", None)
	lang_prob = getattr(info, "language_probability", None)
	try:
		lang_prob = float(lang_prob) if lang_prob is not None else None
	except Exception:
		lang_prob = None

	return TranscriptionResult(
		language=lang,
		language_probability=lang_prob,
		text=full_text,
		segments=segments,
	)
