import logging
import time
from typing import Any

import httpx

from app.core.exceptions import LLMProviderError
from app.core.logging import log_event
from app.llm.base import LLMProvider, LLMResponse, ToolCallRequest

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

logger = logging.getLogger("agentforge.llm")


class GroqProvider(LLMProvider):
    """Talks to Groq's OpenAI-compatible chat-completions API over HTTPX.

    Groq mirrors the OpenAI function-calling wire format (`tools`,
    `tool_choice`, `tool_calls` on the response message), which is what
    makes this a thin adapter rather than bespoke logic scattered through
    the agent.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        body: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            self._log_failure(start, "timeout")
            raise LLMProviderError("The LLM provider timed out.") from exc
        except httpx.HTTPStatusError as exc:
            self._log_failure(start, f"http_{exc.response.status_code}")
            raise LLMProviderError(
                f"The LLM provider returned an error: {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            self._log_failure(start, "connection_error")
            raise LLMProviderError("Could not reach the LLM provider.") from exc

        data = response.json()
        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as exc:
            self._log_failure(start, "malformed_response")
            raise LLMProviderError("The LLM provider returned an unexpected response shape.") from exc

        tool_calls = [
            ToolCallRequest(
                id=call["id"],
                name=call["function"]["name"],
                arguments_json=call["function"]["arguments"],
            )
            for call in message.get("tool_calls") or []
        ]
        usage = data.get("usage") or {}

        log_event(
            logger, logging.INFO, "llm_call",
            llm_model=self._model,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            finish_reason=choice.get("finish_reason"),
            requested_tools=[c.name for c in tool_calls],
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            usage=usage,
        )

    def _log_failure(self, start: float, reason: str) -> None:
        log_event(
            logger, logging.WARNING, "llm_call_failed",
            llm_model=self._model,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            reason=reason,
        )
