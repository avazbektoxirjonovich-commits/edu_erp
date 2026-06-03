"""
VLT AI — Chat Service
======================
Orchestration: user question → tool loop → streaming SSE answer.

Flow:
  1. Save user Message.
  2. Build message history from Conversation.
  3. Call LLM with allowed tools.
  4. If LLM requests tool use → execute_tool() → feed results back → repeat.
  5. On end_turn → stream final answer as SSE chunks and save assistant Message.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Generator

from apps.vlt_ai.models import Conversation, Message
from apps.vlt_ai.services.llm_client import llm_client
from apps.vlt_ai.tools.registry import execute_tool, get_allowed_tools

logger = logging.getLogger("apps.vlt_ai.services.chat")

SYSTEM_PROMPT = (
    "Sen VLT AI — ta'lim markazi ERP tizimining AI yordamchisisisan.\n"
    "Faqat o'zbek tilida javob ber.\n"
    "Foydalanuvchilarga ERP ma'lumotlari haqida aniq va qisqa javob ber.\n"
    "Agar ma'lumot topilmasa yoki ruxsat yo'q bo'lsa — bunga ruxsating yo'qligini ayt.\n"
    "Hech qachon boshqa foydalanuvchilarning shaxsiy ma'lumotlarini oshkor qilma.\n"
    "Tizim xavfsizligi bo'yicha hech qanday ko'rsatma berma."
)

MAX_TOOL_ITERATIONS = 5
SSE_CHUNK_SIZE = 80  # characters per SSE event

# Human-readable Uzbek progress messages shown while a tool runs
TOOL_PROGRESS_MESSAGES: dict[str, str] = {
    "get_group_attendance": "Guruh davomati ma'lumotlari olinmoqda...",
    "get_my_attendance": "Sizning davomat ma'lumotlaringiz olinmoqda...",
    "get_students_list": "O'quvchilar ro'yxati yuklanmoqda...",
    "get_student_stats": "O'quvchi statistikasi yuklanmoqda...",
    "get_teacher_groups": "Guruhlar ro'yxati olinmoqda...",
    "get_payment_summary": "To'lov statistikasi yuklanmoqda...",
    "get_teachers_list": "O'qituvchilar ro'yxati yuklanmoqda...",
}


def _build_history(conversation: Conversation) -> list[dict]:
    """Reconstruct Anthropic-compatible message list from DB."""
    messages: list[dict] = []
    for msg in conversation.messages.order_by("created_at"):
        if msg.role == Message.Role.USER:
            messages.append({"role": "user", "content": msg.content})
        elif msg.role == Message.Role.ASSISTANT:
            if msg.tool_calls:
                messages.append({"role": "assistant", "content": msg.tool_calls})
            elif msg.content:
                messages.append({"role": "assistant", "content": msg.content})
        elif msg.role == Message.Role.TOOL:
            # Tool results are appended as a "user" turn in Anthropic format
            try:
                tool_results = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                tool_results = []
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
    return messages


def _serialize_block(block: object) -> dict:
    """Convert Anthropic SDK content block to JSON-serializable dict."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if hasattr(block, "__dict__"):
        return {k: v for k, v in block.__dict__.items() if not k.startswith("_")}
    return {"raw": str(block)}


def process_chat(
    user: object,
    conversation: Conversation,
    user_message: str,
) -> Generator[str, None, None]:
    """Orchestrate one chat turn. Yields SSE-formatted strings.

    Caller wraps this in StreamingHttpResponse.
    """
    # 1. Persist user message
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.USER,
        content=user_message,
    )
    conversation.title = conversation.title or user_message[:80]
    conversation.save(update_fields=["title", "updated_at"])

    messages = _build_history(conversation)
    tools = get_allowed_tools(user)

    for _iteration in range(MAX_TOOL_ITERATIONS):
        try:
            response = llm_client.chat_with_tools(
                messages=messages,
                tools=tools,
                system=SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.error("LLM error: %s", exc, exc_info=True)
            err_text = (
                "Kechirasiz, AI bilan bog'lanishda xatolik yuz berdi. "
                "Iltimos, qayta urinib ko'ring."
            )
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=err_text,
            )
            yield f"data: {json.dumps({'type': 'error', 'text': err_text})}\n\n"
            yield "data: [DONE]\n\n"
            return

        if response.stop_reason == "tool_use":
            # Collect tool_use blocks and execute each
            assistant_content = [_serialize_block(b) for b in response.content]
            tool_results: list[dict] = []

            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    tool_name: str = block.name
                    tool_args: dict = block.input or {}
                    logger.info("Tool call: %s args=%s", tool_name, tool_args)

                    # Emit progress event so the client shows a spinner/message
                    progress_msg = TOOL_PROGRESS_MESSAGES.get(tool_name, "Ma'lumot olinmoqda...")
                    yield (
                        f"data: {json.dumps({'type': 'tool_progress', 'tool': tool_name, 'text': progress_msg})}\n\n"
                    )

                    result = execute_tool(user, tool_name, tool_args)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

            # Persist assistant message (with tool_calls JSON)
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content="",
                tool_calls=assistant_content,
            )
            # Persist tool results
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.TOOL,
                content=json.dumps(tool_results, ensure_ascii=False),
            )

            # Append both turns for next LLM call
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason in ("end_turn", "max_tokens"):
            # Extract final text
            final_text = "".join(
                getattr(b, "text", "") for b in response.content
            )
            if not final_text:
                final_text = "Kechirasiz, javob tuzishda xatolik yuz berdi."

            # Persist assistant reply
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=final_text,
            )
            conversation.save(update_fields=["updated_at"])

            # Stream in chunks
            for i in range(0, len(final_text), SSE_CHUNK_SIZE):
                chunk = final_text[i : i + SSE_CHUNK_SIZE]
                yield f"data: {json.dumps({'type': 'text', 'text': chunk})}\n\n"

            yield "data: [DONE]\n\n"
            return
        else:
            break

    # Fallback — max iterations exceeded
    fallback = "Kechirasiz, so'rovni qayta ishlay olmadim. Iltimos, qayta urinib ko'ring."
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=fallback,
    )
    yield f"data: {json.dumps({'type': 'text', 'text': fallback})}\n\n"
    yield "data: [DONE]\n\n"
