"""
VLT AI — Pydantic input models for tool validation.
Each model mirrors the tool's input_schema and is used by execute_tool()
to validate LLM-provided arguments before the tool function runs.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class GetGroupAttendanceInput(BaseModel):
    group_id: str
    date_from: str | None = None
    date_to: str | None = None

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from datetime import date

        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"Sana formati noto'g'ri: '{v}'. YYYY-MM-DD formatida kiriting.") from exc
        return v


class GetMyAttendanceInput(BaseModel):
    date_from: str | None = None
    date_to: str | None = None

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        from datetime import date

        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"Sana formati noto'g'ri: '{v}'. YYYY-MM-DD formatida kiriting.") from exc
        return v


class GetStudentsListInput(BaseModel):
    group_id: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|inactive|frozen)$")


class GetStudentStatsInput(BaseModel):
    student_id: str


class GetTeacherGroupsInput(BaseModel):
    teacher_id: str | None = None


class GetPaymentSummaryInput(BaseModel):
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)
    status: str | None = Field(default=None, pattern=r"^(paid|partial|unpaid)$")


class GetTeachersListInput(BaseModel):
    pass


# Registry: tool_name → Pydantic input model class
TOOL_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "get_group_attendance": GetGroupAttendanceInput,
    "get_my_attendance": GetMyAttendanceInput,
    "get_students_list": GetStudentsListInput,
    "get_student_stats": GetStudentStatsInput,
    "get_teacher_groups": GetTeacherGroupsInput,
    "get_payment_summary": GetPaymentSummaryInput,
    "get_teachers_list": GetTeachersListInput,
}
