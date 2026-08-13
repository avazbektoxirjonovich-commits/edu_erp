"""
VLT AI — Tool Schemas (Anthropic tool-use format)
==================================================
All JSON Schema definitions for LLM tool calling.
"""

GROUP_ATTENDANCE_SCHEMA: dict = {
    "name": "get_group_attendance",
    "description": (
        "Guruh davomati statistikasini qaytaradi: "
        "kelgan/kelmagan/kech kelgan/sababli yo'q sonlari va foizi."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "group_id": {
                "type": "string",
                "description": "Guruh UUID identifikatori (majburiy)",
            },
            "date_from": {
                "type": "string",
                "description": "Boshlanish sanasi YYYY-MM-DD formatida (ixtiyoriy)",
            },
            "date_to": {
                "type": "string",
                "description": "Tugash sanasi YYYY-MM-DD formatida (ixtiyoriy)",
            },
        },
        "required": ["group_id"],
    },
}

MY_ATTENDANCE_SCHEMA: dict = {
    "name": "get_my_attendance",
    "description": "O'quvchi o'zining davomat ma'lumotlarini ko'radi.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Boshlanish sanasi YYYY-MM-DD (ixtiyoriy)",
            },
            "date_to": {
                "type": "string",
                "description": "Tugash sanasi YYYY-MM-DD (ixtiyoriy)",
            },
        },
        "required": [],
    },
}

STUDENTS_LIST_SCHEMA: dict = {
    "name": "get_students_list",
    "description": (
        "O'quvchilar ro'yxatini qaytaradi. "
        "Guruh va/yoki holat bo'yicha filtrlash mumkin."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "group_id": {
                "type": "string",
                "description": "Guruh UUID (ixtiyoriy)",
            },
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "frozen"],
                "description": "O'quvchi holati (ixtiyoriy)",
            },
        },
        "required": [],
    },
}

STUDENT_STATS_SCHEMA: dict = {
    "name": "get_student_stats",
    "description": (
        "Bitta o'quvchi bo'yicha batafsil statistika: "
        "davomat foizi, XP ball, daraja, qarz summasi."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "student_id": {
                "type": "string",
                "description": "O'quvchi UUID identifikatori (majburiy)",
            },
        },
        "required": ["student_id"],
    },
}

TEACHER_GROUPS_SCHEMA: dict = {
    "name": "get_teacher_groups",
    "description": (
        "O'qituvchining faol guruhlari ro'yxatini qaytaradi. "
        "Teacher so'rasa — faqat o'z guruhlari ko'rsatiladi."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "teacher_id": {
                "type": "string",
                "description": "O'qituvchi UUID (faqat admin/dev uchun, ixtiyoriy)",
            },
        },
        "required": [],
    },
}

PAYMENT_SUMMARY_SCHEMA: dict = {
    "name": "get_payment_summary",
    "description": (
        "To'lov holati statistikasini qaytaradi: "
        "to'langan, qisman to'langan, to'lanmagan yozuvlar soni va umumiy summa."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {
                "type": "integer",
                "description": "Oy (1-12, ixtiyoriy)",
            },
            "year": {
                "type": "integer",
                "description": "Yil, masalan 2025 (ixtiyoriy)",
            },
            "status": {
                "type": "string",
                "enum": ["paid", "partial", "unpaid"],
                "description": "To'lov holati filtri (ixtiyoriy)",
            },
        },
        "required": [],
    },
}

TEACHERS_LIST_SCHEMA: dict = {
    "name": "get_teachers_list",
    "description": "Faol o'qituvchilar ro'yxatini va ularning guruh sonlarini qaytaradi.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# ── Student self-service ──────────────────────────────────────────

MY_PROFILE_SCHEMA: dict = {
    "name": "get_my_profile",
    "description": "O'quvchi o'zining profil ma'lumotlarini ko'radi: ism, guruh, daraja, XP, Kumush.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

MY_PAYMENTS_SCHEMA: dict = {
    "name": "get_my_payments",
    "description": "O'quvchi o'zining to'lovlar tarixini ko'radi (oxirgi oylar bo'yicha).",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Nechta oxirgi to'lov qaytarilsin (ixtiyoriy, standart 12)",
            },
        },
        "required": [],
    },
}

MY_DEBT_SCHEMA: dict = {
    "name": "get_my_debt",
    "description": "O'quvchi o'zining umumiy qarzini va to'lanmagan/qisman to'lovlarini ko'radi.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

MY_SCHEDULE_SCHEMA: dict = {
    "name": "get_my_schedule",
    "description": "O'quvchi o'zining guruhi dars jadvalini ko'radi (hafta kunlari, vaqt, xona).",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

MY_KUMUSH_SCHEMA: dict = {
    "name": "get_my_kumush",
    "description": "O'quvchi o'zining Kumush balansi va so'nggi Kumush tranzaksiyalarini ko'radi.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

# ── Teacher ─────────────────────────────────────────────────────────

MY_STUDENTS_SCHEMA: dict = {
    "name": "get_my_students",
    "description": "O'qituvchining o'z guruhlaridagi o'quvchilar ro'yxatini qaytaradi.",
    "input_schema": {
        "type": "object",
        "properties": {
            "group_id": {
                "type": "string",
                "description": "Faqat shu guruh (o'qituvchining o'z guruhi bo'lishi kerak, ixtiyoriy)",
            },
        },
        "required": [],
    },
}

# ── Finance ─────────────────────────────────────────────────────────

PAYMENT_REPORT_SCHEMA: dict = {
    "name": "get_payment_report",
    "description": "Moliyachi uchun to'lovlar bo'yicha batafsil hisobot (oy/yil bo'yicha).",
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {"type": "integer", "description": "Oy (1-12, ixtiyoriy, standart joriy oy)"},
            "year": {"type": "integer", "description": "Yil (ixtiyoriy, standart joriy yil)"},
        },
        "required": [],
    },
}

DEBT_REPORT_SCHEMA: dict = {
    "name": "get_debt_report",
    "description": "Qarzdor o'quvchilar hisoboti: eng ko'p qarzi borlar, umumiy qarz summasi.",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Nechta eng katta qarzdor qaytarilsin (ixtiyoriy, standart 10)"},
        },
        "required": [],
    },
}

SALARY_REPORT_SCHEMA: dict = {
    "name": "get_salary_report",
    "description": "O'qituvchilar ish haqi hisoboti (oy/yil bo'yicha, to'langan/kutilayotgan).",
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {"type": "integer", "description": "Oy (1-12, ixtiyoriy, standart joriy oy)"},
            "year": {"type": "integer", "description": "Yil (ixtiyoriy, standart joriy yil)"},
        },
        "required": [],
    },
}

EXPENSE_REPORT_SCHEMA: dict = {
    "name": "get_expense_report",
    "description": "Markaz xarajatlari hisoboti, kategoriya bo'yicha taqsimlangan (oy/yil bo'yicha).",
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {"type": "integer", "description": "Oy (1-12, ixtiyoriy, standart joriy oy)"},
            "year": {"type": "integer", "description": "Yil (ixtiyoriy, standart joriy yil)"},
        },
        "required": [],
    },
}

ASSET_REPORT_SCHEMA: dict = {
    "name": "get_asset_report",
    "description": "Markaz mulklari hisoboti: umumiy qiymat, holat bo'yicha taqsimot.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

FINANCE_SUMMARY_SCHEMA: dict = {
    "name": "get_finance_summary",
    "description": "Umumiy moliyaviy xulosa: daromad, xarajat, ish haqi, sof natija (oy/yil bo'yicha).",
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {"type": "integer", "description": "Oy (1-12, ixtiyoriy, standart joriy oy)"},
            "year": {"type": "integer", "description": "Yil (ixtiyoriy, standart joriy yil)"},
        },
        "required": [],
    },
}

# ── Admin ───────────────────────────────────────────────────────────

STUDENT_STATISTICS_SCHEMA: dict = {
    "name": "get_student_statistics",
    "description": "Barcha o'quvchilar bo'yicha umumiy statistika: holat, guruh taqsimoti.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

ATTENDANCE_STATISTICS_SCHEMA: dict = {
    "name": "get_attendance_statistics",
    "description": "Barcha guruhlar bo'yicha umumiy davomat statistikasi (oy/yil bo'yicha).",
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {"type": "integer", "description": "Oy (1-12, ixtiyoriy)"},
            "year": {"type": "integer", "description": "Yil (ixtiyoriy)"},
        },
        "required": [],
    },
}

# ── Developer diagnostics ────────────────────────────────────────────

ERROR_STATISTICS_SCHEMA: dict = {
    "name": "get_error_statistics",
    "description": "ERP xatoliklari monitoringi bo'yicha umumiy statistika (developer uchun).",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

RECENT_ERRORS_SCHEMA: dict = {
    "name": "get_recent_errors",
    "description": "Eng so'nggi ERP xatoliklari ro'yxati (developer uchun).",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Nechta xatolik qaytarilsin (ixtiyoriy, standart 10)"},
        },
        "required": [],
    },
}
