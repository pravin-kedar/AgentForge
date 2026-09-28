import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import execute_tool_call
from app.agent.state import load_conversation_messages, to_llm_messages
from app.core.exceptions import ToolNotFoundError, ToolValidationError
from app.core.logging import conversation_id_var, log_event, user_id_var
from app.db.models import Conversation, Message, MessageRole, User
from app.llm.base import LLMProvider
from app.tools.registry import get_llm_tool_schemas
from app.tools.validator import validate_tool_call

logger = logging.getLogger("agentforge.agent")

# Hard ceiling on LLM round-trips per turn, independent of the invalid-tool
# retry budget below - protects against a model that keeps calling valid
# tools forever without ever producing a final answer.
MAX_AGENT_ITERATIONS = 8


@dataclass
class AgentResult:
    message: str
    tool_activity: list[str] = field(default_factory=list)


async def _persist(db: AsyncSession, message: Message) -> None:
    db.add(message)
    await db.commit()


async def run_agent_loop(
    db: AsyncSession,
    llm: LLMProvider,
    conversation: Conversation,
    current_user: User,
    user_message: str,
    max_tool_retries: int,
) -> AgentResult:
    """The core agent loop (spec: user -> LLM -> tool? -> validate -> execute
    -> tool result -> LLM -> ... -> final response).

    The LLM only ever decides *which* tool to call and with what arguments;
    everything after that - name/argument validation, authorization,
    execution, and persistence - is backend-controlled.
    """
    # Captured once, up front: a failed tool call triggers a session
    # rollback inside the executor, which expires every object the session
    # is tracking - including `conversation`. Re-reading `conversation.id`
    # after that would trigger an implicit refresh outside of an active
    # async context and crash with MissingGreenlet, so we work off this
    # plain string for the rest of the loop instead of the ORM attribute.
    conversation_id = conversation.id
    # Bind for every log line emitted during this turn (LLM calls, tool
    # executions), so each is attributable without threading ids through.
    user_id_var.set(str(current_user.id))
    conversation_id_var.set(conversation_id)

    await _persist(db, Message(conversation_id=conversation_id, role=MessageRole.USER, content=user_message))

    history = await load_conversation_messages(db, conversation_id)
    messages = to_llm_messages(history)
    tools = get_llm_tool_schemas()

    tool_activity: list[str] = []
    invalid_rounds = 0

    for _iteration in range(MAX_AGENT_ITERATIONS):
        response = await llm.chat(messages, tools=tools)

        if not response.requested_tool_call:
            final_content = response.content or ""
            await _persist(
                db, Message(conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=final_content)
            )
            return AgentResult(message=final_content, tool_activity=tool_activity)

        tool_calls_payload = [
            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments_json}}
            for tc in response.tool_calls
        ]
        await _persist(
            db,
            Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=response.content,
                tool_calls=tool_calls_payload,
            ),
        )
        messages.append({"role": "assistant", "content": response.content, "tool_calls": tool_calls_payload})

        any_invalid_this_round = False

        for tc in response.tool_calls:
            try:
                validated = validate_tool_call(tc)
            except (ToolNotFoundError, ToolValidationError) as exc:
                any_invalid_this_round = True
                log_event(
                    logger, logging.WARNING, "invalid_tool_call",
                    conversation_id=conversation_id, tool_name=tc.name, reason=str(exc),
                )
                error_content = json.dumps({"error": True, "message": str(exc)})
                await _persist(
                    db,
                    Message(
                        conversation_id=conversation_id,
                        role=MessageRole.TOOL,
                        tool_call_id=tc.id,
                        content=error_content,
                    ),
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": error_content})
                continue

            outcome = await execute_tool_call(db, conversation_id, current_user, validated)
            tool_activity.append(outcome.tool_name)
            if outcome.succeeded:
                content = json.dumps({"success": True, "result": outcome.result})
            else:
                content = json.dumps({"error": True, "message": outcome.error_message})
            await _persist(
                db,
                Message(
                    conversation_id=conversation_id, role=MessageRole.TOOL, tool_call_id=tc.id, content=content
                ),
            )
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})

        if any_invalid_this_round:
            invalid_rounds += 1
            if invalid_rounds > max_tool_retries:
                graceful = (
                    "I'm sorry, I wasn't able to complete that request right now. "
                    "Could you rephrase what you'd like me to do?"
                )
                await _persist(
                    db, Message(conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=graceful)
                )
                log_event(
                    logger, logging.ERROR, "tool_retries_exhausted",
                    conversation_id=conversation_id, invalid_rounds=invalid_rounds,
                )
                return AgentResult(message=graceful, tool_activity=tool_activity)

    fallback = "I wasn't able to finish planning that within this turn - could you try narrowing your request?"
    await _persist(db, Message(conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=fallback))
    log_event(logger, logging.WARNING, "agent_iteration_limit_hit", conversation_id=conversation_id)
    return AgentResult(message=fallback, tool_activity=tool_activity)
