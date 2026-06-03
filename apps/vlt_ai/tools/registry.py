"""
VLT AI — Tool Registry
=======================
@ai_tool decorator, TOOL_REGISTRY, get_allowed_tools, execute_tool.

Security model:
  1. get_allowed_tools() — LLM only sees tools the user may call.
  2. execute_tool() — permission re-checked before every execution.
  3. Row-level scoping — each tool function filters its own queryset.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from apps.vlt_ai.permissions import user_can

logger = logging.getLogger("apps.vlt_ai.tools")

# { tool_name: { func, permission, description, schema } }
TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def ai_tool(
    name: str,
    required_permission: str | None = None,
    description: str = "",
    schema: dict | None = None,
) -> Callable:
    """Decorator that registers a function as a VLT AI tool."""

    def decorator(func: Callable) -> Callable:
        TOOL_REGISTRY[name] = {
            "func": func,
            "permission": required_permission,
            "description": description,
            "schema": schema or {},
        }
        return func

    return decorator


def get_allowed_tools(user: Any) -> list[dict]:
    """Return Anthropic-format tool schemas the user is allowed to call."""
    allowed: list[dict] = []
    for spec in TOOL_REGISTRY.values():
        perm = spec["permission"]
        if perm is None or user_can(user, perm):
            allowed.append(spec["schema"])
    return allowed


def _validate_args(name: str, args: dict) -> tuple[dict, str | None]:
    """Validate tool arguments with Pydantic. Returns (clean_args, error_msg)."""
    from apps.vlt_ai.tools.inputs import TOOL_INPUT_MODELS

    model_cls = TOOL_INPUT_MODELS.get(name)
    if model_cls is None:
        return args, None  # no schema registered — pass through

    try:
        from pydantic import ValidationError

        validated = model_cls(**args)
        return validated.model_dump(exclude_none=False), None
    except Exception as exc:  # ValidationError or unexpected
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            msgs = "; ".join(
                f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
                for e in exc.errors()
            )
            return {}, f"Noto'g'ri argumentlar: {msgs}"
        return {}, f"Validatsiya xatosi: {exc}"


def execute_tool(user: Any, name: str, args: dict) -> dict[str, Any]:
    """Execute a tool after permission and Pydantic validation checks.
    Always returns a JSON-safe dict.
    """
    from apps.vlt_ai.models import AILog

    spec = TOOL_REGISTRY.get(name)
    if not spec:
        logger.warning("Tool not found: %s", name)
        return {"error": "Tool topilmadi"}

    perm = spec["permission"]
    if perm and not user_can(user, perm):
        logger.warning("DENIED user=%s tool=%s", user, name)
        AILog.objects.create(
            user=user,
            tool_name=name,
            args=args,
            status=AILog.Status.DENIED,
            result_summary="Ruxsat rad etildi",
        )
        return {"error": "Sizda bunga ruxsat yo'q"}

    # Pydantic validation
    clean_args, validation_error = _validate_args(name, args)
    if validation_error:
        logger.warning("VALIDATION ERROR tool=%s: %s", name, validation_error)
        AILog.objects.create(
            user=user,
            tool_name=name,
            args=args,
            status=AILog.Status.ERROR,
            result_summary=validation_error[:200],
        )
        return {"error": validation_error}

    try:
        result: dict = spec["func"](user=user, **clean_args)
        AILog.objects.create(
            user=user,
            tool_name=name,
            args=args,
            status=AILog.Status.OK,
            result_summary=str(result)[:200],
        )
        logger.info("OK user=%s tool=%s", user, name)
        return result
    except Exception as exc:
        logger.error("ERROR user=%s tool=%s: %s", user, name, exc, exc_info=True)
        AILog.objects.create(
            user=user,
            tool_name=name,
            args=args,
            status=AILog.Status.ERROR,
            result_summary=str(exc)[:200],
        )
        return {"error": f"Tool bajarishda xatolik yuz berdi: {exc}"}
