"""
Error Monitor — Models
========================
ErrorEvent  — one row per distinct error "group" (fingerprint), so repeated
              identical errors do not create hundreds of duplicate records.
ErrorOccurrence — one row per actual occurrence, full technical detail.

Mirrors the existing Payment/PaymentTransaction split already used elsewhere
in this codebase (a summary row + a detail-per-event row).
"""
import uuid

from django.db import models


class ErrorEvent(models.Model):
    """A group of identical (fingerprinted) errors."""

    class Severity(models.TextChoices):
        CRITICAL = 'critical', 'Kritik'
        HIGH     = 'high',     'Yuqori'
        MEDIUM   = 'medium',   "O'rta"
        LOW      = 'low',      'Past'

    class Status(models.TextChoices):
        OPEN          = 'open',          'Ochiq'
        INVESTIGATING = 'investigating',  'Tekshirilmoqda'
        RESOLVED      = 'resolved',      'Hal qilindi'
        IGNORED       = 'ignored',       "E'tiborsiz qoldirildi"

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fingerprint      = models.CharField(max_length=64, unique=True, db_index=True)
    error_type       = models.CharField(max_length=200, verbose_name='Xatolik turi')
    message          = models.TextField(verbose_name="Sanitizatsiya qilingan xabar")
    page             = models.CharField(max_length=300, blank=True, verbose_name='Sahifa')
    endpoint         = models.CharField(max_length=300, blank=True, verbose_name='Endpoint', db_index=True)
    method           = models.CharField(max_length=10, blank=True, verbose_name='HTTP metod')
    status_code      = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='HTTP status')
    severity         = models.CharField(max_length=10, choices=Severity.choices,
                                        default=Severity.MEDIUM, db_index=True, verbose_name='Jiddiylik')
    status           = models.CharField(max_length=15, choices=Status.choices,
                                        default=Status.OPEN, db_index=True, verbose_name='Holat')
    occurrence_count = models.PositiveIntegerField(default=0, verbose_name='Takrorlanish soni')
    first_seen       = models.DateTimeField(auto_now_add=True, verbose_name='Birinchi marta ko\'ringan')
    last_seen        = models.DateTimeField(db_index=True, verbose_name='Oxirgi marta ko\'ringan')

    # Manual AI analysis — cached result of the last developer-triggered
    # analysis. Never populated automatically.
    ai_analysis      = models.JSONField(null=True, blank=True, verbose_name='AI tahlili')
    ai_analyzed_at   = models.DateTimeField(null=True, blank=True)
    ai_analyzed_by   = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='error_analyses_run')

    class Meta:
        verbose_name        = 'Xatolik guruhi'
        verbose_name_plural  = 'Xatolik guruhlari'
        ordering             = ['-last_seen']
        indexes = [
            models.Index(fields=['status', '-last_seen']),
            models.Index(fields=['severity', '-last_seen']),
        ]

    def __str__(self):
        return f"{self.error_type} | {self.endpoint} | x{self.occurrence_count}"


class ErrorOccurrence(models.Model):
    """One actual occurrence of an ErrorEvent, with full technical detail."""

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    error_event  = models.ForeignKey(ErrorEvent, on_delete=models.CASCADE,
                                     related_name='occurrences', verbose_name='Xatolik guruhi')
    user         = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='error_occurrences', verbose_name='Foydalanuvchi')
    user_role    = models.CharField(max_length=20, blank=True, verbose_name='Rol')
    request_id   = models.CharField(max_length=36, blank=True, db_index=True, verbose_name="So'rov ID")
    page         = models.CharField(max_length=300, blank=True, verbose_name='Sahifa')
    endpoint     = models.CharField(max_length=300, blank=True, verbose_name='Endpoint')
    method       = models.CharField(max_length=10, blank=True, verbose_name='HTTP metod')
    status_code  = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='HTTP status')
    sanitized_message = models.TextField(blank=True, verbose_name='Xabar')
    stack_trace  = models.TextField(blank=True, verbose_name='Stack trace')
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Vaqt')

    class Meta:
        verbose_name        = 'Xatolik holati'
        verbose_name_plural  = 'Xatolik holatlari'
        ordering             = ['-created_at']
        indexes = [
            models.Index(fields=['error_event', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.error_event_id} | {self.created_at:%Y-%m-%d %H:%M}"
