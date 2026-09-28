from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import run_agent_loop
from app.agent.state import get_or_create_conversation
from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    llm: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """The one entry point into the agent. The JWT (via `get_current_user`)
    is the sole source of user identity - `payload` never carries a user id,
    and the agent loop below only ever receives `current_user` from here,
    never from anything the LLM produces.
    """
    conversation = await get_or_create_conversation(db, payload.conversation_id, current_user.id)
    # Captured before the agent loop runs: a failed tool call rolls back the
    # shared session partway through, which expires `conversation` - reading
    # `.id` off it afterward would need an implicit refresh outside of an
    # active async context. See app/agent/agent.py for the same guard.
    conversation_id = conversation.id
    result = await run_agent_loop(
        db=db,
        llm=llm,
        conversation=conversation,
        current_user=current_user,
        user_message=payload.message,
        max_tool_retries=settings.max_tool_retries,
    )
    return ChatResponse(conversation_id=conversation_id, message=result.message, tool_activity=result.tool_activity)
