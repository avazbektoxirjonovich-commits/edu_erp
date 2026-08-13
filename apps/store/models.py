import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class StoreItem(models.Model):
    """Mukofotlar do'koni buyumi — o'quvchilar Kumushga almashtiradi."""

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=150, verbose_name='Nomi')
    image       = models.ImageField(upload_to='store/items/', blank=True, null=True, verbose_name='Rasm')
    description = models.TextField(blank=True, verbose_name='Tavsif')
    price       = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name='Narxi (Kumush)')
    stock       = models.PositiveIntegerField(default=0, verbose_name='Qoldiq')
    is_active   = models.BooleanField(default=True, db_index=True, verbose_name='Faol')
    created_by  = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True,
                                    related_name='created_store_items', verbose_name="Kim qo'shdi")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Do'kon buyumi"
        verbose_name_plural  = "Do'kon buyumlari"
        ordering             = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.price} Kumush)"

    @property
    def is_available(self):
        return self.is_active and self.stock > 0


class PurchaseRequest(models.Model):
    """O'quvchining do'kondan buyum so'rovi — admin tasdiqlagandan keyingina beriladi."""

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Kutilmoqda'
        APPROVED  = 'approved',  'Tasdiqlangan / Berildi'
        REJECTED  = 'rejected',  'Rad etildi'
        CANCELLED = 'cancelled', 'Bekor qilindi'
        REFUNDED  = 'refunded',  'Qaytarildi'

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student           = models.ForeignKey('students.Student', on_delete=models.CASCADE,
                                          related_name='store_purchases', verbose_name="O'quvchi")
    item              = models.ForeignKey(StoreItem, on_delete=models.PROTECT,
                                          related_name='purchase_requests', verbose_name='Buyum')
    price_at_request  = models.PositiveIntegerField(verbose_name="So'rov paytidagi narx")
    status            = models.CharField(max_length=10, choices=Status.choices,
                                         default=Status.PENDING, db_index=True)
    requested_at      = models.DateTimeField(auto_now_add=True)
    decided_at        = models.DateTimeField(null=True, blank=True)
    decided_by        = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='store_decisions', verbose_name='Kim hal qildi')
    rejection_reason  = models.CharField(max_length=300, blank=True, verbose_name='Rad etish sababi')
    cancelled_at      = models.DateTimeField(null=True, blank=True)
    refunded_at       = models.DateTimeField(null=True, blank=True)
    refunded_by       = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='store_refunds', verbose_name='Kim qaytardi')
    refund_reason     = models.CharField(max_length=300, blank=True, verbose_name='Qaytarish sababi')

    class Meta:
        verbose_name        = 'Xarid so\'rovi'
        verbose_name_plural  = "Xarid so'rovlari"
        ordering             = ['-requested_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['status', '-requested_at']),
        ]
        constraints = [
            # Bir student bitta buyum uchun bir vaqtning o'zida faqat bitta
            # PENDING so'rovga ega bo'lishi mumkin — tasodifiy takroriy
            # so'rovlarning oldini oladi (DB darajasida, race-safe).
            models.UniqueConstraint(
                fields=['student', 'item'],
                condition=Q(status='pending'),
                name='unique_pending_request_per_student_item',
            ),
        ]

    def __str__(self):
        return f"{self.student} | {self.item} | {self.get_status_display()}"


class KumushTransaction(models.Model):
    """
    Kumush harakati tarixi — HAR BIR kumush harakati (earn yoki spend)
    shu yerda yoziladi: davomat, uyga vazifa, ZUKKO, do'kon xaridi,
    qaytarish, qo'lda tuzatish.
    """

    class Type(models.TextChoices):
        SPEND = 'spend', 'Sarflandi'
        EARN  = 'earn',  "Qo'shildi"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student        = models.ForeignKey('students.Student', on_delete=models.CASCADE,
                                       related_name='kumush_transactions', verbose_name="O'quvchi")
    amount         = models.IntegerField(verbose_name='Miqdor (+/-)')
    type           = models.CharField(max_length=10, choices=Type.choices, db_index=True)
    reason         = models.CharField(max_length=200, verbose_name='Sabab')
    purchase       = models.ForeignKey(PurchaseRequest, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='transactions', verbose_name='Xarid')
    # Forensika: kim, qaysi manba va qaysi obyekt sabab bo'lgani, va
    # tranzaksiyadan oldin/keyingi balans. Eski (tarixiy) yozuvlarda bu
    # maydonlar bo'sh qoladi — fabrikatsiya qilinmaydi.
    created_by     = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='kumush_transactions_created',
                                       verbose_name="Kim amalga oshirdi")
    balance_before = models.PositiveIntegerField(null=True, blank=True, verbose_name='Oldingi balans')
    balance_after  = models.PositiveIntegerField(null=True, blank=True, verbose_name='Keyingi balans')
    source_type    = models.CharField(max_length=30, blank=True, db_index=True, verbose_name='Manba turi')
    source_id      = models.CharField(max_length=64, blank=True, db_index=True, verbose_name='Manba ID')
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = 'Kumush tranzaksiyasi'
        verbose_name_plural  = 'Kumush tranzaksiyalari'
        ordering             = ['-created_at']
        indexes = [
            models.Index(fields=['source_type', 'source_id']),
        ]

    def __str__(self):
        return f"{self.student} | {self.amount:+d} | {self.reason}"
