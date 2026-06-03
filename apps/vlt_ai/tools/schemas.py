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
