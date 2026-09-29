from app.agent.state import to_llm_messages
from app.db.models import Message, MessageRole


def test_to_llm_messages_reconstructs_roles_in_order() -> None:
    history = [
        Message(conversation_id="c1", role=MessageRole.SYSTEM, content="system prompt"),
        Message(conversation_id="c1", role=MessageRole.USER, content="hi"),
        Message(
            conversation_id="c1",
            role=MessageRole.ASSISTANT,
            content=None,
            tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}],
        ),
        Message(conversation_id="c1", role=MessageRole.TOOL, tool_call_id="call_1", content='{"success": true}'),
        Message(conversation_id="c1", role=MessageRole.ASSISTANT, content="It's sunny in Goa."),
    ]

    messages = to_llm_messages(history)

    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool", "assistant"]
    assert messages[2]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert messages[3]["tool_call_id"] == "call_1"
    assert messages[4]["content"] == "It's sunny in Goa."
