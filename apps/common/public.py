"""
Public API (autentifikatsiyasiz) uchun umumiy yordamchilar.

Musobaqa ro'yxati ham, o'quv markazga ariza ham bir xil himoyadan foydalanadi:
IP aniqlash, telefon normalizatsiyasi, ism tekshiruvi, honeypot maydoni.
"""
import ipaddress
import re

# Formadagi ko'rinmas maydon — bot to'ldirsa, so'rov jim rad etiladi
HONEYPOT_FIELD = 'website'

NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʻʼ'‘’`\- ]{2,60}$")


def client_ip(request):
    """Mijoz IP'si. Railway proxy'si X-Forwarded-For'ga haqiqiy IP'ni OXIRIDAN qo'shadi —
    oldingi qismini mijoz o'zi yozishi mumkin, shuning uchun faqat oxirgisi olinadi."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    candidate = xff.split(',')[-1].strip() if xff else ''
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return request.META.get('REMOTE_ADDR')


def normalize_phone(value):
    """'90 123 45 67', '998901234567', '+998 (90) 123-45-67' → '+998901234567'."""
    digits = re.sub(r'[\s\-()]', '', value or '')
    if digits.startswith('+'):
        return digits
    if len(digits) == 9 and digits.isdigit():
        return '+998' + digits
    if len(digits) == 12 and digits.startswith('998'):
        return '+' + digits
    return digits
