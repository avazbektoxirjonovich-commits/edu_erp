"""
CORS: public sayt (PUBLIC_SITE_ORIGIN) faqat /api/public/ yo'llariga murojaat qila oladi.
ERP'ning o'z CORS sozlamalari (CORS_ALLOWED_ORIGINS) o'zgarmaydi.
"""
from corsheaders.signals import check_request_enabled
from django.conf import settings


def allow_public_site(sender, request, **kwargs):
    origin = request.headers.get('Origin', '')
    allowed = getattr(settings, 'PUBLIC_SITE_ORIGIN', '')
    return bool(allowed) and origin == allowed and request.path.startswith('/api/public/')


check_request_enabled.connect(allow_public_site, dispatch_uid='musobaqalar_public_cors')
