import logging

from django.apps import AppConfig

logger = logging.getLogger('apps.face_auth')


class FaceAuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'apps.face_auth'
    verbose_name       = 'Yuz autentifikatsiyasi'

    def ready(self):
        """Startup checks: warn about missing model files, never crash."""
        self._check_face_landmarker()
        self._check_encryption_key()

    def _check_face_landmarker(self):
        import pathlib, os
        from django.conf import settings
        custom = (
            os.environ.get('FACE_LANDMARKER_MODEL', '')
            or getattr(settings, 'FACE_LANDMARKER_MODEL', '')
        )
        path = pathlib.Path(custom) if custom else (
            pathlib.Path(__file__).resolve().parent
            / 'models_weights' / 'face_landmarker.task'
        )
        if not path.exists():
            logger.warning(
                "DIQQAT: face_landmarker.task topilmadi (%s). "
                "MediaPipe landmark tekshiruvi o'chiriladi. "
                "Yuklab olish: "
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                "face_landmarker/float16/1/face_landmarker.task "
                "Yoki FACE_LANDMARKER_MODEL env o'zgaruvchisi bilan sozlang.",
                path,
            )

    def _check_encryption_key(self):
        from django.conf import settings
        key = getattr(settings, 'FACE_ENCRYPTION_KEY', '') or ''
        if getattr(settings, 'FACE_AUTH_ENABLED', False) and not key:
            logger.warning(
                "DIQQAT: FACE_AUTH_ENABLED=True lekin FACE_ENCRYPTION_KEY o'rnatilmagan! "
                "Face ID ro'yxatga olish ishlamaydi. "
                "Kalit yaratish: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
