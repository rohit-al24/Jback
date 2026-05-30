from django.contrib import admin

from .models import MasterPayments, SubscriptionPlan


@admin.register(MasterPayments)
class MasterPaymentsAdmin(admin.ModelAdmin):
    list_display = ('id', 'enabled', 'updated_at')
    list_editable = ('enabled',)

    def has_add_permission(self, request):
        # Keep this table singleton-ish: only one row should exist.
        if MasterPayments.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price_inr', 'duration_days', 'is_active', 'created_at')
    list_editable = ('is_active',)
