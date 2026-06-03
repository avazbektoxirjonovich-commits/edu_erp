from django.apps import AppConfig


class VltAiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.vlt_ai"
    verbose_name = "VLT AI"

    def ready(self) -> None:
        # Configure structured logging for VLT AI
        from apps.vlt_ai.logging_config import configure_structlog

        configure_structlog()
        # Self-register all tools by importing tool modules
        import apps.vlt_ai.tools  # noqa: F401
