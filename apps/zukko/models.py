import random
import uuid

from django.conf import settings
from django.db import models


class ChallengeCategory(models.Model):
    """Bug-find va coding topshiriqlarni mavzu bo'yicha guruhlash uchun kategoriya."""

    name = models.CharField("Nomi", max_length=200)
    slug = models.SlugField("Slug", unique=True)
    description = models.TextField("Tavsif", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='zukko_created_categories', verbose_name="Yaratuvchi"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zukko'
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Difficulty(models.TextChoices):
    EASY = 'easy', 'Oson'
    MEDIUM = 'medium', "O'rta"
    HARD = 'hard', 'Qiyin'


DIFFICULTY_MULTIPLIER = {'easy': 1, 'medium': 2, 'hard': 3}


class BugFindChallenge(models.Model):
    """ZUKKO'ning noyob xususiyati: xatoli kodni topish topshirig'i."""

    class BugType(models.TextChoices):
        SYNTAX = 'syntax', 'Sintaksis xatosi'
        LOGIC = 'logic', 'Mantiqiy xato'
        RUNTIME = 'runtime', 'Runtime xato'
        INDENTATION = 'indentation', 'Indentatsiya xatosi'
        TYPE_ERROR = 'type_error', 'Tip xatosi'
        INDEX_ERROR = 'index_error', 'Indeks xatosi'
        INFINITE_LOOP = 'infinite_loop', 'Cheksiz tsikl'
        OFF_BY_ONE = 'off_by_one', 'Off-by-one xato'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Sarlavha", max_length=300)
    description = models.TextField("Masala sharti")
    category = models.ForeignKey(
        ChallengeCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bugfind_challenges',
        verbose_name="Kategoriya"
    )
    buggy_code = models.TextField("Xatoli kod", help_text="O'quvchiga ko'rsatiladi")
    correct_code = models.TextField("To'g'ri kod", help_text="Tekshirish uchun, talabaga ko'rsatilmaydi")
    bug_line_number = models.PositiveIntegerField("Xato qatori", help_text="1-dan boshlab sanaladi")
    bug_explanation = models.TextField("Xato tushuntirishi", help_text="Javobdan keyin ko'rsatiladi")
    difficulty = models.CharField("Qiyinlik", max_length=6, choices=Difficulty.choices, default=Difficulty.EASY)
    bug_type = models.CharField("Xato turi", max_length=20, choices=BugType.choices, default=BugType.LOGIC)
    programming_language = models.CharField("Dasturlash tili", max_length=30, default='python')
    time_limit_seconds = models.PositiveIntegerField("Vaqt chegarasi (soniya)", default=300)
    points = models.PositiveIntegerField("Asosiy ball", default=10)
    hint = models.TextField("Maslahat", blank=True, help_text="Ko'rsatilsa -2 ball ayriladi")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='zukko_created_bugfind', verbose_name="Yaratuvchi"
    )
    is_active = models.BooleanField("Aktiv", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'zukko'
        verbose_name = "Bug-find topshiriq"
        verbose_name_plural = "Bug-find topshiriqlar"
        ordering = ['-created_at']

    def get_points(self):
        return self.points * DIFFICULTY_MULTIPLIER.get(self.difficulty, 1)

    def __str__(self):
        return f"[{self.get_difficulty_display()}] {self.title}"


class CodingChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Sarlavha", max_length=300)
    description = models.TextField("Tavsif")
    category = models.ForeignKey(
        ChallengeCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='coding_challenges',
        verbose_name="Kategoriya"
    )
    constraints = models.TextField("Cheklovlar", blank=True)
    input_format = models.TextField("Kirish formati")
    output_format = models.TextField("Chiqish formati")
    sample_input = models.TextField("Namuna kirish", blank=True)
    sample_output = models.TextField("Namuna chiqish", blank=True)
    sample_explanation = models.TextField("Namuna tushuntirishi", blank=True)
    hidden_test_cases = models.JSONField(
        "Yashirin testlar", default=list,
        help_text='[{"input": "...", "expected_output": "..."}, ...] formatda'
    )
    starter_code = models.TextField("Boshlang'ich shablon", blank=True, default='')
    solution_code = models.TextField("Yechim kodi", help_text="Faqat o'qituvchiga ko'rinadi")
    difficulty = models.CharField("Qiyinlik", max_length=6, choices=Difficulty.choices, default=Difficulty.EASY)
    programming_language = models.CharField("Dasturlash tili", max_length=30, default='python')
    time_limit_seconds = models.PositiveIntegerField("Vaqt chegarasi (soniya)", default=1800)
    memory_limit_mb = models.PositiveIntegerField("Xotira chegarasi (MB)", default=256)
    points = models.PositiveIntegerField("Ball", default=20)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='zukko_created_coding', verbose_name="Yaratuvchi"
    )
    is_active = models.BooleanField("Aktiv", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'zukko'
        verbose_name = "Coding topshiriq"
        verbose_name_plural = "Coding topshiriqlar"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_difficulty_display()}] {self.title}"


class ChallengeSession(models.Model):
    """Ustoz yaratadi, o'quvchilar share_link orqali kiradi."""

    class SessionType(models.TextChoices):
        QUIZ = 'quiz', 'Test'
        BUGFIND = 'bugfind', 'Bug-find'
        CODING = 'coding', 'Coding'
        MIXED = 'mixed', 'Aralash'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Qoralama'
        ACTIVE = 'active', 'Aktiv'
        COMPLETED = 'completed', 'Tugagan'
        ARCHIVED = 'archived', 'Arxivlangan'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Nomi", max_length=300)
    session_type = models.CharField(
        "Turi", max_length=10, choices=SessionType.choices, default=SessionType.MIXED
    )
    status = models.CharField(
        "Holat", max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    # ERP: groups.Group → Group.teacher → teachers.Teacher → Teacher.user → User
    group = models.ForeignKey(
        'groups.Group', on_delete=models.CASCADE,
        related_name='challenge_sessions', verbose_name="Guruh",
        null=True, blank=True,
    )
    bugfind_pool = models.ManyToManyField(
        BugFindChallenge, blank=True, related_name='sessions', verbose_name="Bug-find pool"
    )
    coding_pool = models.ManyToManyField(
        CodingChallenge, blank=True, related_name='sessions', verbose_name="Coding pool"
    )
    bugfind_count = models.PositiveIntegerField("Bug-find savollar soni (random)", default=5)
    coding_count = models.PositiveIntegerField("Coding savollar soni (random)", default=3)
    time_limit_minutes = models.PositiveIntegerField("Vaqt chegarasi (daqiqa)", default=45)
    starts_at = models.DateTimeField("Boshlanish vaqti", null=True, blank=True)
    ends_at = models.DateTimeField("Tugash vaqti", null=True, blank=True)
    anti_paste_enabled = models.BooleanField("Copy-paste taqiqlash", default=True)
    tab_switch_limit = models.PositiveIntegerField("Tab almashtirish limiti", default=3)
    shuffle_questions = models.BooleanField("Savollarni aralashtirish", default=True)
    share_link = models.CharField("Havola kodi", max_length=100, unique=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='zukko_created_sessions', verbose_name="Yaratuvchi"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zukko'
        verbose_name = "Challenge sessiya"
        verbose_name_plural = "Challenge sessiyalar"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.share_link:
            self.share_link = uuid.uuid4().hex[:12]
        super().save(*args, **kwargs)

    def get_random_challenges(self):
        bugfind_pool = list(self.bugfind_pool.all())
        if not bugfind_pool:
            bugfind_pool = list(BugFindChallenge.objects.filter(is_active=True))
        coding_pool = list(self.coding_pool.all())
        if not coding_pool:
            coding_pool = list(CodingChallenge.objects.filter(is_active=True))
        bugfind = random.sample(bugfind_pool, min(self.bugfind_count, len(bugfind_pool)))
        coding = random.sample(coding_pool, min(self.coding_count, len(coding_pool)))
        return bugfind, coding

    def __str__(self):
        group_name = self.group.name if self.group else '—'
        return f"[{self.get_status_display()}] {self.title} ({group_name})"


class ChallengeSubmission(models.Model):
    class SubmissionType(models.TextChoices):
        BUGFIND = 'bugfind', 'Bug-find'
        CODING = 'coding', 'Coding'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        CORRECT = 'correct', "To'g'ri"
        PARTIAL = 'partial', 'Qisman'
        WRONG = 'wrong', "Noto'g'ri"
        TIME_EXPIRED = 'time_expired', 'Vaqt tugadi'
        CHEATING = 'cheating', 'Aldash aniqlandi'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='zukko_submissions', verbose_name="Talaba"
    )
    session = models.ForeignKey(
        ChallengeSession, on_delete=models.CASCADE,
        related_name='submissions', verbose_name="Sessiya",
        null=True, blank=True
    )
    submission_type = models.CharField(
        "Topshiriq turi", max_length=10, choices=SubmissionType.choices
    )
    bugfind_challenge = models.ForeignKey(
        BugFindChallenge, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='submissions', verbose_name="Bug-find topshiriq"
    )
    coding_challenge = models.ForeignKey(
        CodingChallenge, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='submissions', verbose_name="Coding topshiriq"
    )
    submitted_code = models.TextField("Yuborilgan kod", blank=True)
    identified_line = models.PositiveIntegerField(
        "Topilgan qator", null=True, blank=True, help_text="Bug-find uchun"
    )
    status = models.CharField(
        "Holat", max_length=15, choices=Status.choices, default=Status.PENDING
    )
    points_earned = models.PositiveIntegerField("Olingan ball", default=0)
    test_results = models.JSONField(
        "Test natijalari", default=dict, blank=True
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField("Yuborilgan vaqt", null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField("Sarflangan vaqt (soniya)", default=0)
    keystroke_log = models.JSONField("Klaviatura logi", default=list, blank=True)
    suspicion_score = models.FloatField("Shubha darajasi", default=0.0)
    ip_address = models.GenericIPAddressField("IP manzil", null=True, blank=True)

    class Meta:
        app_label = 'zukko'
        verbose_name = "Topshiriq javobi"
        verbose_name_plural = "Topshiriq javoblari"
        ordering = ['-started_at']

    def __str__(self):
        name = self.user.full_name if self.user else '—'
        return f"{name}: {self.get_submission_type_display()} → {self.get_status_display()}"


class AntiCheatEvent(models.Model):
    class EventType(models.TextChoices):
        PASTE = 'paste', 'Copy-paste'
        TAB_SWITCH = 'tab_switch', 'Tab almashtirish'
        FOCUS_LOSS = 'focus_loss', "Fokus yo'qotish"
        RIGHT_CLICK = 'right_click', "O'ng tugma"
        RAPID_TYPE = 'rapid_type', "G'ayritabiiy tezkor yozish"
        BULK_INSERT = 'bulk_insert', "Ko'p qatorli qo'shish"
        DEVTOOLS = 'devtools', "DevTools ochildi"
        IDLE_LONG = 'idle_long', "Uzoq harakatsizlik"
        SIMILARITY = 'similarity', "O'xshashlik (plagiat)"
        IP_SHARED = 'ip_shared', "Bir xil IP'dan boshqa talaba"
        SCREEN_RECORD = 'screen_record', "Ekran yozish urinishi"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        ChallengeSubmission, on_delete=models.CASCADE,
        related_name='anticheat_events', verbose_name="Javob",
        null=True, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='zukko_anticheat_events', verbose_name="Talaba"
    )
    event_type = models.CharField("Hodisa turi", max_length=15, choices=EventType.choices)
    severity = models.FloatField("Jiddiylik", default=0.1)
    details = models.JSONField("Tafsilotlar", default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zukko'
        verbose_name = "Anti-cheat hodisa"
        verbose_name_plural = "Anti-cheat hodisalar"
        ordering = ['-timestamp']

    def __str__(self):
        name = self.user.full_name if self.user else '—'
        return f"{name}: {self.get_event_type_display()} ({self.severity})"


class StudentProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='zukko_progress', verbose_name="Talaba"
    )
    # topic FK olib tashlandi — ERP'da topics.Topic app yo'q
    category = models.ForeignKey(
        ChallengeCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='student_progress', verbose_name="Kategoriya"
    )
    total_attempts = models.PositiveIntegerField("Jami urinishlar", default=0)
    correct_count = models.PositiveIntegerField("To'g'ri", default=0)
    wrong_count = models.PositiveIntegerField("Noto'g'ri", default=0)
    partial_count = models.PositiveIntegerField("Qisman", default=0)
    easy_solved = models.PositiveIntegerField("Oson yechilgan", default=0)
    medium_solved = models.PositiveIntegerField("O'rta yechilgan", default=0)
    hard_solved = models.PositiveIntegerField("Qiyin yechilgan", default=0)
    total_time_seconds = models.PositiveIntegerField("Jami vaqt (soniya)", default=0)
    avg_time_seconds = models.PositiveIntegerField("O'rtacha vaqt (soniya)", default=0)
    fastest_solve_seconds = models.PositiveIntegerField("Eng tez yechim (soniya)", default=0)
    total_points = models.PositiveIntegerField("Jami ball", default=0)
    total_xp = models.PositiveIntegerField("Jami XP", default=0)
    mastery_percentage = models.FloatField("O'zlashtirish foizi", default=0.0)
    daily_stats = models.JSONField("Kunlik statistika", default=dict, blank=True)
    error_breakdown = models.JSONField("Xato turlari taqsimoti", default=dict, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'zukko'
        verbose_name = "Talaba progressi"
        verbose_name_plural = "Talabalar progressi"
        # topic olib tashlandi — unique_together faqat (user, category)
        unique_together = ('user', 'category')

    def total_solved(self):
        return self.easy_solved + self.medium_solved + self.hard_solved

    def update_mastery(self):
        if self.total_attempts == 0:
            self.mastery_percentage = 0.0
            return
        base = (self.correct_count + self.partial_count * 0.5) / self.total_attempts * 100
        difficulty_bonus = min(self.hard_solved * 2 + self.medium_solved * 1, 15)
        self.mastery_percentage = round(min(base + difficulty_bonus, 100), 1)

    def __str__(self):
        name = self.user.full_name if self.user else '—'
        return f"{name}: {self.mastery_percentage}% ({self.total_solved()} ta)"
