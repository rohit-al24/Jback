from django.apps import AppConfig


def _connect_post_migrate_handlers():
    from django.db.models.signals import post_migrate

    from .roles import ensure_role_groups

    post_migrate.connect(ensure_role_groups, dispatch_uid="core.ensure_role_groups")


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self) -> None:
        from . import signals  # noqa: F401
        _connect_post_migrate_handlers()
