# Self-register all tools by importing their modules.
from apps.vlt_ai.tools import (  # noqa: F401
    attendance,
    diagnostics,
    finance,
    groups,
    kumush,
    payments,
    statistics,
    students,
    teachers,
)
