from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import Mondai, MondaiQuestion, MondaiVocabulary


class MondaiForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # UI requirement: remove "Embed" from dropdown and present "Link" as "YouTube".
        # We keep the model field as-is for backward compatibility.
        vt = self.fields.get("video_type")
        if vt is not None:
            vt.choices = [
                (Mondai.VideoType.UPLOAD, "Upload"),
                (Mondai.VideoType.LINK, "YouTube"),
            ]

        # If editing legacy records that used EMBED, show them as YouTube and prefill URL.
        if getattr(self.instance, "video_type", None) == Mondai.VideoType.EMBED:
            self.initial["video_type"] = Mondai.VideoType.LINK
            if not self.initial.get("video_url"):
                self.initial["video_url"] = getattr(self.instance, "video_embed_url", "")

    class Meta:
        model = Mondai
        fields = [
            "name",
            "video_type",
            "video_file",
            "video_url",
            "transcript",
        ]
        widgets = {
            "transcript": forms.Textarea(attrs={"rows": 6}),
        }

    def clean(self):
        cleaned = super().clean()
        video_type = cleaned.get("video_type")
        video_file = cleaned.get("video_file")
        video_url = cleaned.get("video_url")

        if video_type == Mondai.VideoType.UPLOAD:
            if not video_file and not (self.instance and self.instance.video_file):
                self.add_error("video_file", "Please upload a video")

        if video_type == Mondai.VideoType.LINK:
            if not video_url:
                self.add_error("video_url", "Please provide a video link")

        # If this was a legacy EMBED Mondai being edited, convert to LINK.
        if getattr(self.instance, "video_type", None) == Mondai.VideoType.EMBED and video_type == Mondai.VideoType.LINK:
            # Prefer whatever user typed; else fall back to stored embed url.
            if not video_url:
                cleaned["video_url"] = getattr(self.instance, "video_embed_url", "")

        return cleaned

    def save(self, commit=True):
        instance: Mondai = super().save(commit=False)
        # Ensure legacy EMBED records get migrated to LINK upon save.
        if instance.video_type == Mondai.VideoType.EMBED:
            instance.video_type = Mondai.VideoType.LINK
            if not instance.video_url and instance.video_embed_url:
                instance.video_url = instance.video_embed_url
        if commit:
            instance.save()
            self.save_m2m()
        return instance


MondaiVocabFormSet = inlineformset_factory(
    Mondai,
    MondaiVocabulary,
    fields=("term", "reading", "meaning", "order"),
    extra=1,
    can_delete=True,
)


class MondaiQuestionForm(forms.ModelForm):
    class Meta:
        model = MondaiQuestion
        fields = (
            "prompt",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_answer",
            "order",
        )
        widgets = {
            "prompt": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        option_d = (cleaned.get("option_d") or "").strip()
        correct = cleaned.get("correct_answer")
        if not option_d and correct == MondaiQuestion.CorrectAnswer.D:
            self.add_error("correct_answer", "Option D is empty; pick A/B/C or fill D")
        return cleaned


MondaiQuestionFormSet = inlineformset_factory(
    Mondai,
    MondaiQuestion,
    form=MondaiQuestionForm,
    extra=1,
    can_delete=True,
)
