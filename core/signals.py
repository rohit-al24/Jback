from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import VideoCompletion
from .xp import award_xp


@receiver(post_save, sender=VideoCompletion)
def award_points_for_video_completion(sender, instance: VideoCompletion, created: bool, **kwargs):
    if not created:
        return

    award_xp(user_id=instance.user_id, points=50, reason="video_completed")
