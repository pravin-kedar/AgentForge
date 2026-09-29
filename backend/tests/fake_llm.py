import json
from typing import Any

from app.llm.base import LLMProvider, LLMResponse, ToolCallRequest


class FakeLLMProvider(LLMProvider):
    """Deterministic stand-in for a real LLM, used by every test so the
    suite never depends on network access or a live Groq key.

    Configure it with a list of `LLMResponse`s (or plain dicts, converted
    below) to return in sequence, one per `chat()` call - mirroring a
    scripted multi-turn tool-calling conversation.
    """

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, Any]]] = []

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("FakeLLMProvider ran out of scripted responses")
        return self.responses.pop(0)


def final_text(content: str) -> LLMResponse:
    return LLMResponse(content=content, tool_calls=[])


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCallRequest(id=call_id, name=name, arguments_json=json.dumps(arguments))],
    )
