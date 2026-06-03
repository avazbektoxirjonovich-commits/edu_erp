"""
VLT AI — Models
================
Conversation, Message, AILog
"""
import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """A chat session between a user and VLT AI."""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
                     settings.AUTH_USER_MODEL,
                     on_delete=models.CASCADE,
                     related_name="ai_conversations",
                     verbose_name="Foydalanuvchi",
                 )
    title      = models.CharField(max_length=200, blank=True, verbose_name="Sarlavha")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Suhbat"
        verbose_name_plural = "Suhbatlar"
        ordering            = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user} | {self.title or 'Nomsiz'}"


class Message(models.Model):
    """A single message in a Conversation."""

    class Role(models.TextChoices):
        USER      = "user",      "Foydalanuvchi"
        ASSISTANT = "assistant", "AI"
        TOOL      = "tool",      "Tool natijasi"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
                       Conversation,
                       on_delete=models.CASCADE,
                       related_name="messages",
                       verbose_name="Suhbat",
                   )
    role         = models.CharField(
                       max_length=10,
                       choices=Role.choices,
                       default=Role.USER,
                       verbose_name="Rol",
                   )
    content      = models.TextField(blank=True, verbose_name="Mazmun")
    tool_calls   = models.JSONField(
                       null=True, blank=True,
                       verbose_name="Tool chaqiruvlari",
                   )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Xabar"
        verbose_name_plural = "Xabarlar"
        ordering            = ["created_at"]

    def __str__(self) -> str:
        return f"{self.conversation} | {self.role} | {self.content[:50]}"


class AILog(models.Model):
    """Audit log for every tool call attempt (OK, DENIED, ERROR)."""

    class Status(models.TextChoices):
        OK     = "OK",     "Muvaffaqiyatli"
        DENIED = "DENIED", "Rad etildi"
        ERROR  = "ERROR",  "Xatolik"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user           = models.ForeignKey(
                         settings.AUTH_USER_MODEL,
                         on_delete=models.SET_NULL,
                         null=True,
                         related_name="ai_logs",
                         verbose_name="Foydalanuvchi",
                     )
    tool_name      = models.CharField(max_length=100, verbose_name="Tool nomi", db_index=True)
    args           = models.JSONField(default=dict, verbose_name="Argumentlar")
    status         = models.CharField(
                         max_length=6,
                         choices=Status.choices,
                         default=Status.OK,
                         db_index=True,
                         verbose_name="Holat",
                     )
    result_summary = models.CharField(max_length=500, blank=True, verbose_name="Natija xulosasi")
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = "AI Jurnal"
        verbose_name_plural = "AI Jurnali"
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tool_name", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} | {self.tool_name} | {self.status} | {self.created_at:%Y-%m-%d %H:%M}"
