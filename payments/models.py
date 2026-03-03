from __future__ import annotations

from django.db import models


class MasterPayments(models.Model):
    """Singleton-ish table used as a global feature flag.

    If enabled=True: subscription paywall + locks are active.
    If enabled=False: app runs fully unlocked (free mode), and payment flows should be disabled.
    """

    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Master Payments'
        verbose_name_plural = 'Master Payments'

    def __str__(self) -> str:
        return 'MasterPayments(enabled=%s)' % ('True' if self.enabled else 'False')


def payments_enabled() -> bool:
    """Return global payments feature flag; defaults to True."""
    obj = MasterPayments.objects.order_by('id').first()
    return bool(obj.enabled) if obj else True
