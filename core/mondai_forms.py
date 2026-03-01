from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import Mondai, MondaiQuestion, MondaiVocabulary


class MondaiForm(forms.ModelForm):
    class Meta:
        model = Mondai
        fields = [
            "name",
            "video_type",
            "video_file",
            "video_url",
            "video_embed_url",
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
        video_embed_url = cleaned.get("video_embed_url")

        if video_type == Mondai.VideoType.UPLOAD:
            if not video_file and not (self.instance and self.instance.video_file):
                self.add_error("video_file", "Please upload a video")

        if video_type == Mondai.VideoType.LINK:
            if not video_url:
                self.add_error("video_url", "Please provide a video link")

        if video_type == Mondai.VideoType.EMBED:
            if not video_embed_url:
                self.add_error("video_embed_url", "Please provide an embed URL")

        return cleaned


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
