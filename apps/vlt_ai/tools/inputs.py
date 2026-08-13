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


class GetMyProfileInput(BaseModel):
    pass


class GetMyPaymentsInput(BaseModel):
    limit: int | None = Field(default=12, ge=1, le=60)


class GetMyDebtInput(BaseModel):
    pass


class GetMyScheduleInput(BaseModel):
    pass


class GetMyKumushInput(BaseModel):
    pass


class GetMyStudentsInput(BaseModel):
    group_id: str | None = None


class GetPaymentReportInput(BaseModel):
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)


class GetDebtReportInput(BaseModel):
    limit: int | None = Field(default=10, ge=1, le=100)


class GetSalaryReportInput(BaseModel):
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)


class GetExpenseReportInput(BaseModel):
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)


class GetAssetReportInput(BaseModel):
    pass


class GetFinanceSummaryInput(BaseModel):
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)


class GetStudentStatisticsInput(BaseModel):
    pass


class GetAttendanceStatisticsInput(BaseModel):
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)


class GetErrorStatisticsInput(BaseModel):
    pass


class GetRecentErrorsInput(BaseModel):
    limit: int | None = Field(default=10, ge=1, le=50)


# Registry: tool_name → Pydantic input model class
TOOL_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "get_group_attendance": GetGroupAttendanceInput,
    "get_my_attendance": GetMyAttendanceInput,
    "get_students_list": GetStudentsListInput,
    "get_student_stats": GetStudentStatsInput,
    "get_teacher_groups": GetTeacherGroupsInput,
    "get_payment_summary": GetPaymentSummaryInput,
    "get_teachers_list": GetTeachersListInput,
    "get_my_profile": GetMyProfileInput,
    "get_my_payments": GetMyPaymentsInput,
    "get_my_debt": GetMyDebtInput,
    "get_my_schedule": GetMyScheduleInput,
    "get_my_kumush": GetMyKumushInput,
    "get_my_students": GetMyStudentsInput,
    "get_payment_report": GetPaymentReportInput,
    "get_debt_report": GetDebtReportInput,
    "get_salary_report": GetSalaryReportInput,
    "get_expense_report": GetExpenseReportInput,
    "get_asset_report": GetAssetReportInput,
    "get_finance_summary": GetFinanceSummaryInput,
    "get_student_statistics": GetStudentStatisticsInput,
    "get_attendance_statistics": GetAttendanceStatisticsInput,
    "get_error_statistics": GetErrorStatisticsInput,
    "get_recent_errors": GetRecentErrorsInput,
}
