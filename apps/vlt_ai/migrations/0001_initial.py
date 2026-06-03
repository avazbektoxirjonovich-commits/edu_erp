import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(blank=True, max_length=200, verbose_name="Sarlavha")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_conversations",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Foydalanuvchi",
                    ),
                ),
            ],
            options={
                "verbose_name": "Suhbat",
                "verbose_name_plural": "Suhbatlar",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "role",
                    models.CharField(
                        choices=[("user", "Foydalanuvchi"), ("assistant", "AI"), ("tool", "Tool natijasi")],
                        default="user",
                        max_length=10,
                        verbose_name="Rol",
                    ),
                ),
                ("content", models.TextField(blank=True, verbose_name="Mazmun")),
                ("tool_calls", models.JSONField(blank=True, null=True, verbose_name="Tool chaqiruvlari")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="vlt_ai.conversation",
                        verbose_name="Suhbat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Xabar",
                "verbose_name_plural": "Xabarlar",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="AILog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tool_name", models.CharField(db_index=True, max_length=100, verbose_name="Tool nomi")),
                ("args", models.JSONField(default=dict, verbose_name="Argumentlar")),
                (
                    "status",
                    models.CharField(
                        choices=[("OK", "Muvaffaqiyatli"), ("DENIED", "Rad etildi"), ("ERROR", "Xatolik")],
                        db_index=True,
                        default="OK",
                        max_length=6,
                        verbose_name="Holat",
                    ),
                ),
                ("result_summary", models.CharField(blank=True, max_length=500, verbose_name="Natija xulosasi")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Foydalanuvchi",
                    ),
                ),
            ],
            options={
                "verbose_name": "AI Jurnal",
                "verbose_name_plural": "AI Jurnali",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="ailog",
            index=models.Index(fields=["user", "status"], name="vlt_ai_ailo_user_id_status_idx"),
        ),
        migrations.AddIndex(
            model_name="ailog",
            index=models.Index(fields=["tool_name", "status"], name="vlt_ai_ailo_tool_status_idx"),
        ),
    ]
