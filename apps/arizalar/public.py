"""
PUBLIC API — saytdan o'quv markazga ariza qoldirish (autentifikatsiyasiz).

  POST /api/public/ariza/   — ariza qoldirish

Himoya (musobaqa ro'yxati bilan bir xil):
  - IP bo'yicha throttle ('ariza_register' scope)
  - bitta IP'dan soatiga ko'pi bilan MAX_APPLICATIONS_PER_IP_HOUR ta ariza (bazaga asoslangan)
  - honeypot: ko'rinmas 'website' maydoni to'ldirilgan bo'lsa — bot, jim rad etiladi
  - ochiq arizasi bor telefon raqamdan takror ariza qabul qilinmaydi
  - CORS faqat PUBLIC_SITE_ORIGIN uchun va faqat /api/public/ yo'llarida
    (apps/musobaqalar/signals.py — barcha public yo'llarga tegishli)
"""
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.common.public import HONEYPOT_FIELD, client_ip, normalize_phone

from .models import Application

MAX_APPLICATIONS_PER_IP_HOUR = getattr(settings, 'ARIZA_MAX_PER_IP_HOUR', 5)

# To'liq ism (ism familiya otasining ismi) — harflar, bo'sh joy, chiziqcha, apostrof
FULL_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʻʼ'‘’`\- ]{5,150}$")

ACCEPTED_MESSAGE = ("Arizangiz qabul qilindi! Tez orada operatorimiz siz bilan "
                    "bog'lanib, batafsil ma'lumot beradi.")
DUPLICATE_MESSAGE = ("Bu telefon raqam bilan ariza allaqachon qoldirilgan — "
                     "tez orada siz bilan bog'lanamiz.")


class ArizaThrottle(AnonRateThrottle):
    scope = 'ariza_register'

    def get_ident(self, request):
        return client_ip(request)


class ApplicationSerializer(serializers.Serializer):
    """JSON kalitlari sayt bilan kelishilgan — o'zbekcha."""
    ism_familya     = serializers.CharField(max_length=150, trim_whitespace=True)
    telefon         = serializers.CharField(max_length=25)
    yashash_manzili = serializers.CharField(max_length=300, trim_whitespace=True)
    ota_ona_ismi    = serializers.CharField(max_length=150, trim_whitespace=True)
    yosh            = serializers.IntegerField(min_value=3, max_value=99)
    yonalish        = serializers.CharField(max_length=100, trim_whitespace=True)

    def _name(self, value, label):
        value = re.sub(r'\s+', ' ', value).strip()
        if not FULL_NAME_RE.match(value):
            raise serializers.ValidationError(
                f"{label} faqat harflardan iborat bo'lsin (5-150 belgi).")
        return value

    def validate_ism_familya(self, value):
        return self._name(value, 'Ism familiya')

    def validate_ota_ona_ismi(self, value):
        return self._name(value, "Ota-ona ismi")

    def validate_telefon(self, value):
        phone = normalize_phone(value)
        if not re.fullmatch(r'\+998\d{9}', phone):
            raise serializers.ValidationError("Telefon raqam +998901234567 ko'rinishida bo'lsin.")
        return phone

    def validate_yashash_manzili(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Yashash manzilini to'liqroq yozing.")
        return value

    def validate_yonalish(self, value):
        value = re.sub(r'\s+', ' ', value).strip()
        if len(value) < 2:
            raise serializers.ValidationError("Qaysi yo'nalishda o'qimoqchi ekaningizni yozing.")
        return value

    def validate(self, data):
        if Application.objects.filter(phone=data['telefon'],
                                      status__in=Application.OPEN_STATUSES).exists():
            raise serializers.ValidationError({'telefon': [DUPLICATE_MESSAGE]})
        return data


class ArizaCreateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ArizaThrottle]

    def post(self, request):
        # Honeypot: bot ko'rinmas maydonni to'ldiradi — muvaffaqiyat javobi, lekin hech narsa yozilmaydi
        if str(request.data.get(HONEYPOT_FIELD, '')).strip():
            return Response({'xabar': ACCEPTED_MESSAGE}, status=status.HTTP_201_CREATED)

        ip = client_ip(request)
        hour_ago = timezone.now() - timedelta(hours=1)
        if ip and Application.objects.filter(ip_address=ip, created_at__gte=hour_ago).count() \
                >= MAX_APPLICATIONS_PER_IP_HOUR:
            return Response({'detail': "Juda ko'p so'rov. Birozdan keyin qayta urinib ko'ring."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)

        serializer = ApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        Application.objects.create(
            full_name=d['ism_familya'], phone=d['telefon'], address=d['yashash_manzili'],
            parent_name=d['ota_ona_ismi'], age=d['yosh'], direction=d['yonalish'],
            ip_address=ip,
        )
        return Response({'xabar': ACCEPTED_MESSAGE}, status=status.HTTP_201_CREATED)
