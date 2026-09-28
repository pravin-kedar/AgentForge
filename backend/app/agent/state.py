from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import SYSTEM_PROMPT
from app.core.exceptions import NotFoundError
from app.db.models import Conversation, Message, MessageRole


async def load_conversation_messages(db: AsyncSession, conversation_id: str) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    )
    return list(result.scalars().all())


def to_llm_messages(history: list[Message]) -> list[dict[str, Any]]:
    """Reconstruct the OpenAI/Groq-format message list from stored rows.

    The stored system prompt is never trusted as-is from the DB for new
    turns (callers should ensure a system message is only persisted once,
    at conversation creation) - this function simply replays whatever was
    actually stored, in order.
    """
    messages: list[dict[str, Any]] = []
    for msg in history:
        if msg.role == MessageRole.SYSTEM:
            messages.append({"role": "system", "content": msg.content or ""})
        elif msg.role == MessageRole.USER:
            messages.append({"role": "user", "content": msg.content or ""})
        elif msg.role == MessageRole.ASSISTANT:
            entry: dict[str, Any] = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            messages.append(entry)
        elif msg.role == MessageRole.TOOL:
            messages.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content or ""})
    return messages


def new_conversation_seed() -> list[dict[str, Any]]:
    return [{"role": "system", "content": SYSTEM_PROMPT}]


async def get_or_create_conversation(
    db: AsyncSession, conversation_id: str | None, user_id: int
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is not None:
            return conversation
        raise NotFoundError(f"No conversation with id '{conversation_id}' for this user.")

    conversation = Conversation(user_id=user_id)
    db.add(conversation)
    await db.flush()

    db.add(Message(conversation_id=conversation.id, role=MessageRole.SYSTEM, content=SYSTEM_PROMPT))
    await db.flush()
    return conversation
