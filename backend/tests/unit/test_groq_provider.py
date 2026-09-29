import json

import httpx
import pytest

from app.core.exceptions import LLMProviderError
from app.llm.groq import GroqProvider


def _provider(handler) -> GroqProvider:
    return GroqProvider(
        api_key="k", model="m", base_url="https://example.test/v1", transport=httpx.MockTransport(handler)
    )


async def test_parses_plain_text_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    response = await _provider(handler).chat([{"role": "user", "content": "hi"}])

    assert response.content == "Hello!"
    assert response.tool_calls == []
    assert response.usage["prompt_tokens"] == 10


async def test_parses_tool_calls_and_sends_tools_in_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "get_weather", "arguments": '{"destination": "Goa"}'},
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    response = await _provider(handler).chat([{"role": "user", "content": "weather?"}], tools=tools)

    assert captured["body"]["tools"] == tools
    assert captured["body"]["tool_choice"] == "auto"
    assert captured["auth"] == "Bearer k"
    assert response.requested_tool_call
    assert response.tool_calls[0].name == "get_weather"
    assert response.tool_calls[0].arguments_json == '{"destination": "Goa"}'


async def test_http_error_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(LLMProviderError):
        await _provider(handler).chat([{"role": "user", "content": "hi"}])


async def test_timeout_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMProviderError, match="timed out"):
        await _provider(handler).chat([{"role": "user", "content": "hi"}])


async def test_malformed_response_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    with pytest.raises(LLMProviderError):
        await _provider(handler).chat([{"role": "user", "content": "hi"}])
