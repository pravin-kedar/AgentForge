from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.models import Conversation, Message, MessageRole, User

# Roles that are safe to show a user in their own conversation history.
# System-role messages (the internal prompt) are never returned to the frontend.
_VISIBLE_ROLES = {MessageRole.USER, MessageRole.ASSISTANT}


def visible_messages(conversation: Conversation) -> list[Message]:
    """Filter to user-facing messages without touching the ORM-managed
    `.messages` collection - reassigning that list would trigger the
    relationship's delete-orphan cascade and delete the filtered-out rows.
    """
    return [m for m in conversation.messages if m.role in _VISIBLE_ROLES]


async def list_conversations(db: AsyncSession, user: User) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation_detail(db: AsyncSession, user: User, conversation_id: str) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise NotFoundError(f"No conversation with id '{conversation_id}'.")
    return conversation


async def delete_conversation(db: AsyncSession, user: User, conversation_id: str) -> None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise NotFoundError(f"No conversation with id '{conversation_id}'.")
    await db.delete(conversation)
    await db.commit()
