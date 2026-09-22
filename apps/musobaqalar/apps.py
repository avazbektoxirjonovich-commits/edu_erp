from django.apps import AppConfig


class MusobaqalarConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.musobaqalar'
    verbose_name = 'Musobaqalar'

    def ready(self):
        from . import signals  # noqa: F401  (public sayt uchun CORS)
