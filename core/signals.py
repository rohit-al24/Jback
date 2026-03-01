from __future__ import annotations

from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, VideoCompletion


@receiver(post_save, sender=VideoCompletion)
def award_points_for_video_completion(sender, instance: VideoCompletion, created: bool, **kwargs):
    if not created:
        return

    # Concurrency-safe increment.
    User.objects.filter(pk=instance.user_id).update(total_points=F("total_points") + 50)
