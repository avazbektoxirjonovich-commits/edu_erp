"""
iOS "Web Clip" konfiguratsiya profili (.mobileconfig).

iPhone/iPad'da Android'dagi "o'rnatish" oynasi yo'q (beforeinstallprompt
faqat Chrome/Android'da bor). Shu sababli iOS uchun profil fayli beriladi:
foydalanuvchi saytdan faylni yuklab oladi -> Sozlamalar -> "Profil yuklab
olindi" -> O'rnatish -> bosh ekranda logotipli ikonka paydo bo'ladi va
bosilganda ERP to'liq ekranda (brauzer manzil qatorisiz) ochiladi.

Apple hujjati: Configuration Profile Reference, "Web Clip Payload"
(PayloadType = com.apple.webClip.managed).
"""
import plistlib
import uuid
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse

# Profil identifikatorlari — o'zgarmas bo'lishi kerak: foydalanuvchi profilni
# qayta o'rnatganda iOS eskisining ustiga yozadi, ikkinchi ikonka chiqmaydi.
PROFILE_ID = 'uz.qorakolilmziyo.erp'
WEBCLIP_ID = 'uz.qorakolilmziyo.erp.webclip'
_NAMESPACE = uuid.UUID('6f9619ff-8b86-d011-b42d-00c04fc964ff')

ICON_PATH = Path(settings.BASE_DIR) / 'static' / 'icons' / 'icon-192.png'
CONTENT_TYPE = 'application/x-apple-aspen-config'
FILENAME = 'qorakol-ilm-ziyo.mobileconfig'

APP_NAME = "Qorako'l Ilm Ziyo"
_CACHE: dict[str, bytes] = {}


def _icon_bytes() -> bytes | None:
    """Bosh ekrandagi ikonka (PNG). Fayl bo'lmasa iOS standart ikonka qo'yadi."""
    try:
        return ICON_PATH.read_bytes()
    except OSError:
        return None


def _stable_uuid(base_url: str, suffix: str) -> str:
    """Manzilga bog'langan o'zgarmas UUID (har deploy'da bir xil)."""
    return str(uuid.uuid5(_NAMESPACE, f'{base_url}#{suffix}')).upper()


def build_webclip_profile(base_url: str) -> bytes:
    """`base_url` ni bosh ekranga qo'shadigan .mobileconfig faylini qaytaradi."""
    base_url = base_url.rstrip('/') + '/'
    if base_url in _CACHE:
        return _CACHE[base_url]

    webclip = {
        'PayloadType': 'com.apple.webClip.managed',
        'PayloadVersion': 1,
        'PayloadIdentifier': WEBCLIP_ID,
        'PayloadUUID': _stable_uuid(base_url, 'webclip'),
        'PayloadDisplayName': APP_NAME,
        'URL': base_url,
        'Label': APP_NAME,
        'IsRemovable': True,        # foydalanuvchi ikonkani o'chira oladi
        'FullScreen': True,         # brauzer manzil qatorisiz ochiladi
        'IgnoreManifestScope': True,  # ichki havolalar ham to'liq ekranda
        'Precomposed': True,        # iOS ikonkaga o'z effektini qo'shmaydi
    }
    icon = _icon_bytes()
    if icon:
        webclip['Icon'] = icon

    profile = {
        'PayloadType': 'Configuration',
        'PayloadVersion': 1,
        'PayloadIdentifier': PROFILE_ID,
        'PayloadUUID': _stable_uuid(base_url, 'profile'),
        'PayloadDisplayName': f"{APP_NAME} — ERP ilovasi",
        'PayloadDescription': "Bosh ekranga ERP ikonkasini qo'shadi. "
                              "Boshqa hech qanday sozlama o'zgarmaydi.",
        'PayloadOrganization': APP_NAME,
        'PayloadRemovalDisallowed': False,
        'PayloadContent': [webclip],
    }
    data = plistlib.dumps(profile, fmt=plistlib.FMT_XML)
    _CACHE[base_url] = data
    return data


def ios_webclip(request):
    """GET /ios-app.mobileconfig — iPhone uchun bosh ekran ikonkasi profili."""
    data = build_webclip_profile(request.build_absolute_uri('/'))
    resp = HttpResponse(data, content_type=CONTENT_TYPE)
    resp['Content-Disposition'] = f'attachment; filename="{FILENAME}"'
    resp['Cache-Control'] = 'public, max-age=3600'
    return resp
