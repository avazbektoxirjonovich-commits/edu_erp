"""
VLT AI — LLM Client
====================
Provider-agnostic wrapper. Currently backed by Anthropic Claude.
Provider and model are read from environment variables so they can be
swapped without touching code.

Environment variables:
  VLT_AI_PROVIDER   = anthropic  (default; only "anthropic" supported now)
  VLT_AI_MODEL      = claude-haiku-4-5-20251001  (default)
  VLT_AI_MAX_TOKENS = 1024  (default)
  ANTHROPIC_API_KEY = <required for anthropic provider>
"""
from __future__ import annotations

import logging
import os
from collections.abc import Generator
from typing import Any

logger = logging.getLogger("apps.vlt_ai.services.llm_client")


class LLMClient:
    """Provider-agnostic LLM client with tool-calling and streaming support."""

    def __init__(self) -> None:
        self.provider: str = os.environ.get("VLT_AI_PROVIDER", "anthropic")
        self.model: str = os.environ.get("VLT_AI_MODEL", "claude-haiku-4-5-20251001")
        self.max_tokens: int = int(os.environ.get("VLT_AI_MAX_TOKENS", "1024"))
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            if self.provider == "anthropic":
                try:
                    import anthropic  # type: ignore[import]
                except ImportError as exc:
                    raise ImportError(
                        "anthropic paketi topilmadi. "
                        "Iltimos: pip install anthropic"
                    ) from exc
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                if not api_key:
                    raise ValueError(
                        "ANTHROPIC_API_KEY muhiti o'zgaruvchisi topilmadi. "
                        ".env fayliga qo'shing."
                    )
                self._client = anthropic.Anthropic(api_key=api_key)
            else:
                raise ValueError(
                    f"Noma'lum LLM provayder: {self.provider!r}. "
                    "Hozircha faqat 'anthropic' qo'llab-quvvatlanadi."
                )
        return self._client

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system: str = "",
    ) -> Any:
        """Non-streaming call that may request tool use. Returns raw API response."""
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)
        logger.info(
            "LLM call model=%s stop_reason=%s input_tokens=%s output_tokens=%s",
            self.model,
            response.stop_reason,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return response

    def stream_text(
        self,
        messages: list[dict],
        system: str = "",
    ) -> Generator[str, None, None]:
        """Streaming call — yields text chunks. No tool calling."""
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        with client.messages.stream(**kwargs) as stream:
            yield from stream.text_stream


# Module-level singleton
llm_client = LLMClient()
