from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    """A single tool call the model asked for. `arguments_json` is the raw,
    unparsed JSON string the model produced - it may be malformed, so parsing
    and validation happen downstream in the tool validator, not here.
    """

    id: str
    name: str
    arguments_json: str


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def requested_tool_call(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstraction over a chat-completions LLM backend with tool/function calling.

    The agent runtime depends only on this interface, never on a specific
    vendor, so a new provider (OpenAI, Azure OpenAI, ...) can be added by
    implementing `chat()` without touching `app/agent/*`.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a chat-completion request and return the parsed response."""
        raise NotImplementedError
