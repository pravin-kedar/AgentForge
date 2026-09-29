from httpx import AsyncClient


async def test_register_returns_token(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "new-user@example.com", "password": "password123"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "new-user@example.com"


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "password123"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_success(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "login@example.com", "password": "password123"})
    response = await client.post("/auth/login", json={"email": "login@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "login2@example.com", "password": "password123"})
    response = await client.post("/auth/login", json={"email": "login2@example.com", "password": "wrong-pass"})
    assert response.status_code == 401


async def test_chat_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/chat", json={"message": "hi"})
    assert response.status_code == 401
