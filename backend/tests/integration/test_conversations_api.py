from httpx import AsyncClient

from tests.fake_llm import FakeLLMProvider, final_text


async def test_list_conversations_empty_initially(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/conversations", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_conversation_detail_hides_system_prompt(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str]
) -> None:
    fake_llm.responses.append(final_text("Hello there!"))
    chat_response = await client.post("/api/v1/chat", json={"message": "hi"}, headers=auth_headers)
    conversation_id = chat_response.json()["conversation_id"]

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()

    roles = [m["role"] for m in body["messages"]]
    assert "system" not in roles
    assert roles == ["user", "assistant"]


async def test_cannot_access_another_users_conversation(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str]
) -> None:
    fake_llm.responses.append(final_text("Hello there!"))
    chat_response = await client.post("/api/v1/chat", json={"message": "hi"}, headers=auth_headers)
    conversation_id = chat_response.json()["conversation_id"]

    other_register = await client.post(
        "/auth/register", json={"email": "someone-else@example.com", "password": "password123"}
    )
    other_headers = {"Authorization": f"Bearer {other_register.json()['access_token']}"}

    response = await client.get(f"/api/v1/conversations/{conversation_id}", headers=other_headers)
    assert response.status_code == 404


async def test_delete_conversation(
    client: AsyncClient, fake_llm: FakeLLMProvider, auth_headers: dict[str, str]
) -> None:
    fake_llm.responses.append(final_text("Hello there!"))
    chat_response = await client.post("/api/v1/chat", json={"message": "hi"}, headers=auth_headers)
    conversation_id = chat_response.json()["conversation_id"]

    delete_response = await client.delete(f"/api/v1/conversations/{conversation_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_headers)
    assert get_response.status_code == 404
