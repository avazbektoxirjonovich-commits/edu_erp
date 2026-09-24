"""
PUBLIC API — alohida public sayt uchun (autentifikatsiyasiz).

  GET  /api/public/musobaqa/joriy/                 — e'lon qilingan musobaqa (yo'q bo'lsa musobaqa: null)
  POST /api/public/musobaqa/royxat/                — ro'yxatdan o'tish
  GET  /api/public/musobaqa/natijalar/oxirgi/      — oxirgi yakunlangan musobaqa natijalari
  GET  /api/public/musobaqa/natijalar/<uuid>/      — yakunlangan musobaqa natijalari (sinf bo'yicha TOP-10; sinfsizlar — umumiy)

Himoya:
  - IP bo'yicha throttle (DRF, 'musobaqa_register' / 'musobaqa_public' scope'lari)
  - bitta IP'dan soatiga ko'pi bilan MAX_REGISTRATIONS_PER_IP_HOUR ta ro'yxat (bazaga asoslangan —
    gunicorn jarayonlari va qayta ishga tushishdan qat'i nazar ishlaydi)
  - honeypot: formadagi ko'rinmas 'website' maydoni to'ldirilgan bo'lsa — bot, jim rad etiladi
  - CORS faqat PUBLIC_SITE_ORIGIN uchun va faqat /api/public/ yo'llarida (signals.py)
"""
import re
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.common.public import HONEYPOT_FIELD, NAME_RE, client_ip, normalize_phone  # noqa: F401

from .models import Competition, Participant, Result

MAX_REGISTRATIONS_PER_IP_HOUR = getattr(settings, 'MUSOBAQA_MAX_REGISTRATIONS_PER_IP_HOUR', 10)
TOP_PER_GRADE = 10


class PublicThrottle(AnonRateThrottle):
    scope = 'musobaqa_public'

    def get_ident(self, request):
        return client_ip(request)


class RegisterThrottle(PublicThrottle):
    scope = 'musobaqa_register'


def masked_name(participant, full):
    if full:
        return participant.first_name, participant.last_name
    return participant.first_name, f"{participant.last_name[:1]}."


# ── Serializerlar (JSON kalitlari public sayt bilan kelishilgan — o'zbekcha) ──────────────
class PublicCompetitionSerializer(serializers.ModelSerializer):
    nomi                    = serializers.CharField(source='name')
    boshlanish_sinf         = serializers.IntegerField(source='grade_from')
    tugash_sinf             = serializers.IntegerField(source='grade_to')
    manzil                  = serializers.CharField(source='location')
    # ISO 8601 + vaqt zonasi — brauzerlar (Safari ham) Date() bilan xatosiz o'qiydi
    royxatdan_otish_muddati = serializers.DateTimeField(source='registration_deadline', format='iso-8601')
    musobaqa_sanasi         = serializers.DateTimeField(source='competition_date', format='iso-8601')
    royxat_ochiq            = serializers.BooleanField(source='is_registration_open')

    class Meta:
        model  = Competition
        fields = ['id', 'nomi', 'boshlanish_sinf', 'tugash_sinf', 'manzil',
                  'royxatdan_otish_muddati', 'musobaqa_sanasi', 'royxat_ochiq']


class RegistrationSerializer(serializers.Serializer):
    musobaqa_id     = serializers.UUIDField()
    ism             = serializers.CharField(max_length=60, trim_whitespace=True)
    familya         = serializers.CharField(max_length=60, trim_whitespace=True)
    telefon         = serializers.CharField(max_length=25)
    yashash_manzili = serializers.CharField(max_length=300, trim_whitespace=True)
    # Ixtiyoriy — saytdagi formada so'ralmaydi
    sinf            = serializers.IntegerField(min_value=1, max_value=11, required=False, allow_null=True)

    def _name(self, value, label):
        value = re.sub(r'\s+', ' ', value)
        if not NAME_RE.match(value):
            raise serializers.ValidationError(f"{label} faqat harflardan iborat bo'lsin (2-60 belgi).")
        return value

    def validate_ism(self, value):
        return self._name(value, 'Ism')

    def validate_familya(self, value):
        return self._name(value, 'Familya')

    def validate_telefon(self, value):
        phone = normalize_phone(value)
        if not re.fullmatch(r'\+998\d{9}', phone):
            raise serializers.ValidationError("Telefon raqam +998901234567 ko'rinishida bo'lsin.")
        return phone

    def validate_yashash_manzili(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Yashash manzilini to'liqroq yozing.")
        return value

    def validate(self, data):
        competition = Competition.objects.filter(pk=data['musobaqa_id']).first()
        if not competition or competition.status != Competition.Status.PUBLISHED:
            raise serializers.ValidationError({'musobaqa_id': ["Bu musobaqaga ro'yxatdan o'tib bo'lmaydi."]})
        if timezone.now() > competition.registration_deadline:
            raise serializers.ValidationError({'musobaqa_id': ["Ro'yxatdan o'tish muddati tugagan."]})
        if data.get('sinf') is not None and not competition.accepts_grade(data['sinf']):
            raise serializers.ValidationError({'sinf': [
                f"Bu musobaqa {competition.grade_from}-{competition.grade_to} sinflar uchun."]})
        if Participant.objects.filter(competition=competition, phone=data['telefon']).exists():
            raise serializers.ValidationError({'telefon': [
                "Bu telefon raqam bilan ushbu musobaqaga allaqachon ro'yxatdan o'tilgan."]})
        data['competition'] = competition
        return data


# ── View'lar ────────────────────────────────────────────────────────────────────
class PublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicThrottle]


class CurrentCompetitionView(PublicView):
    def get(self, request):
        competition = Competition.objects.filter(status=Competition.Status.PUBLISHED).first()
        return Response({'musobaqa': PublicCompetitionSerializer(competition).data if competition else None})


REGISTERED_MESSAGE = "Siz ro'yxatdan o'tdingiz! Tez orada operatorimiz sizga qo'ng'iroq qilib tasdiqlaydi."


class RegisterView(PublicView):
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        # Honeypot: bot ko'rinmas maydonni to'ldiradi — muvaffaqiyat javobi qaytadi, hech narsa yozilmaydi
        if str(request.data.get(HONEYPOT_FIELD, '')).strip():
            return Response({'xabar': REGISTERED_MESSAGE}, status=status.HTTP_201_CREATED)

        ip = client_ip(request)
        hour_ago = timezone.now() - timedelta(hours=1)
        if ip and Participant.objects.filter(ip_address=ip, registered_at__gte=hour_ago).count() \
                >= MAX_REGISTRATIONS_PER_IP_HOUR:
            return Response({'detail': "Juda ko'p so'rov. Birozdan keyin qayta urinib ko'ring."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)

        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            with transaction.atomic():
                Participant.objects.create(
                    competition=d['competition'], first_name=d['ism'], last_name=d['familya'],
                    phone=d['telefon'], address=d['yashash_manzili'], grade=d.get('sinf'), ip_address=ip,
                )
        except IntegrityError:
            # Bir vaqtda ikki marta yuborilgan forma
            return Response({'telefon': ["Bu telefon raqam bilan ushbu musobaqaga allaqachon ro'yxatdan o'tilgan."]},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'xabar': REGISTERED_MESSAGE}, status=status.HTTP_201_CREATED)


def results_payload(competition):
    rows = (Result.objects.filter(participant__competition=competition)
            .select_related('participant')
            .order_by(F('participant__grade').asc(nulls_last=True), F('place').asc(nulls_last=True), '-score'))
    by_grade = defaultdict(list)
    for r in rows:
        items = by_grade[r.participant.grade]
        if len(items) >= TOP_PER_GRADE:
            continue
        ism, familya = masked_name(r.participant, competition.show_full_names)
        items.append({'ism': ism, 'familya': familya, 'ball': r.score, 'orin': r.place})
    return {
        'musobaqa': {'id': str(competition.pk), 'nomi': competition.name,
                     'musobaqa_sanasi': (timezone.localtime(competition.competition_date).isoformat()
                                         if competition.competition_date else None)},
        # sinf: null — sinfi ko'rsatilmagan ishtirokchilar (umumiy reyting)
        'sinflar': [{'sinf': g, 'natijalar': by_grade[g]}
                    for g in sorted(by_grade, key=lambda g: (g is None, g or 0))],
    }


class ResultsView(PublicView):
    def get(self, request, pk):
        competition = Competition.objects.filter(pk=pk, status=Competition.Status.FINISHED).first()
        if not competition:
            return Response({'detail': "Bu musobaqa natijalari hali e'lon qilinmagan."},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(results_payload(competition))


class LatestResultsView(PublicView):
    """Public saytdagi "Oldingi g'oliblar" bo'limi uchun — oxirgi yakunlangan musobaqa."""

    def get(self, request):
        competition = (Competition.objects.filter(status=Competition.Status.FINISHED)
                       .order_by('-competition_date', '-updated_at').first())
        if not competition:
            return Response({'musobaqa': None, 'sinflar': []})
        return Response(results_payload(competition))
