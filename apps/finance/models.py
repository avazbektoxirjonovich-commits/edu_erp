import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PaymentTransaction(models.Model):
    """
    Bitta to'lov operatsiyasi (chek).
    Bir Payment (oylik hisob) bir nechta PaymentTransaction'ga ega bo'lishi
    mumkin — shu orqali qisman to'lovlar alohida-alohida yoziladi.
    Payment.paid_amount shu yozuvlar yig'indisidan avtomatik yangilanadi
    (qarang: apps/finance/signals.py).
    """

    class PaymentType(models.TextChoices):
        CASH     = 'cash',     'Naqd'
        CARD     = 'card',     'Karta'
        TRANSFER = 'transfer', "O'tkazma"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment        = models.ForeignKey(
                         'payments.Payment', on_delete=models.CASCADE,
                         related_name='transactions', verbose_name="To'lov hisobi",
                         db_index=True,
                     )
    amount         = models.DecimalField(
                         max_digits=10, decimal_places=0,
                         validators=[MinValueValidator(1)],
                         verbose_name='Summa',
                     )
    payment_type   = models.CharField(max_length=10, choices=PaymentType.choices,
                                      default=PaymentType.CASH, verbose_name="To'lov turi")
    receipt_number = models.CharField(max_length=30, unique=True, editable=False,
                                      verbose_name='Chek raqami')
    note           = models.CharField(max_length=200, blank=True, verbose_name='Izoh')
    received_by    = models.ForeignKey(
                         'accounts.User', on_delete=models.SET_NULL, null=True,
                         related_name='finance_transactions', verbose_name='Qabul qildi',
                     )
    # Payment.debt_amount ning shu tranzaksiya paytidagi qotgan nusxasi — chekda
    # ko'rsatish uchun. Keyinroq boshqa to'lovlar qo'shilsa ham o'zgarmasligi kerak,
    # aks holda eski chek qayta ochilganda noto'g'ri qarz ko'rsatib qoladi.
    debt_after     = models.DecimalField(
                         max_digits=10, decimal_places=0, null=True, blank=True,
                         verbose_name="Shu to'lovdan keyingi qarz",
                     )
    paid_at        = models.DateTimeField(default=timezone.now, verbose_name="To'lov vaqti")
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "To'lov operatsiyasi"
        verbose_name_plural = "To'lov operatsiyalari"
        ordering            = ['-paid_at']

    def __str__(self):
        return f"{self.receipt_number} | {self.payment} | {self.amount}"

    def _generate_receipt_number(self):
        return f"QIZ{self.paid_at.strftime('%y%m%d')}{uuid.uuid4().hex[:6].upper()}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self._generate_receipt_number()
        super().save(*args, **kwargs)


class Expense(models.Model):
    """Markaz xarajati (ijara, internet, reklama va h.k.)."""

    class Category(models.TextChoices):
        RENT        = 'rent',        'Ijara'
        INTERNET    = 'internet',    'Internet'
        ADVERTISING = 'advertising', 'Reklama'
        EQUIPMENT   = 'equipment',   'Jihoz'
        REPAIR      = 'repair',      "Ta'mirlash"
        UTILITIES   = 'utilities',   'Kommunal'
        SALARY      = 'salary',      'Ish haqi'
        OTHER       = 'other',       'Boshqa'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=150, verbose_name='Xarajat nomi')
    category     = models.CharField(max_length=20, choices=Category.choices,
                                    default=Category.OTHER, verbose_name='Kategoriya',
                                    db_index=True)
    amount       = models.DecimalField(max_digits=12, decimal_places=0,
                                       validators=[MinValueValidator(1)], verbose_name='Summa')
    expense_date = models.DateField(verbose_name='Sana', db_index=True)
    description  = models.TextField(blank=True, verbose_name='Tavsif')
    created_by   = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                     related_name='created_expenses', verbose_name="Kim qo'shdi")
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Xarajat'
        verbose_name_plural = 'Xarajatlar'
        ordering            = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.name} | {self.amount} | {self.expense_date}"


class Asset(models.Model):
    """Markaz mulki (jihoz, mebel va h.k.) — ombor tizimi emas, oddiy ro'yxat."""

    class Condition(models.TextChoices):
        NEW          = 'new',          'Yangi'
        GOOD         = 'good',         'Yaxshi'
        NEEDS_REPAIR = 'needs_repair', "Ta'mir talab qiladi"
        DAMAGED      = 'damaged',      'Shikastlangan'
        DISPOSED     = 'disposed',     'Chiqarib tashlangan'

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name           = models.CharField(max_length=150, verbose_name='Mulk nomi')
    category       = models.CharField(max_length=100, blank=True, verbose_name='Kategoriya')
    quantity       = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)],
                                                 verbose_name='Miqdor')
    purchase_date  = models.DateField(null=True, blank=True, verbose_name='Sotib olingan sana')
    purchase_price = models.DecimalField(max_digits=12, decimal_places=0, default=0,
                                         verbose_name='Narxi (dona)')
    condition      = models.CharField(max_length=15, choices=Condition.choices,
                                      default=Condition.NEW, verbose_name='Holati',
                                      db_index=True)
    notes          = models.TextField(blank=True, verbose_name='Izoh')
    created_by     = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                       related_name='created_assets', verbose_name="Kim qo'shdi")
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Mulk'
        verbose_name_plural = 'Mulklar'
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.name} x{self.quantity}"

    @property
    def total_value(self):
        return self.quantity * self.purchase_price
