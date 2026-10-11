import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_login_single_session(client: AsyncClient):
    # 1. Register
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "student1@example.com",
            "password": "supersecret123",
            "first_name": "Aline",
            "last_name": "K",
            "school_name": "Kigali High",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "student1@example.com"

    # 2. Login #1
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "student1@example.com", "password": "supersecret123"},
    )
    assert r.status_code == 200, r.text
    cookie1 = r.cookies.get("clh_session")
    assert cookie1

    # 3. /me works with first session
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200

    # 4. Login #2 — should invalidate session #1
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "student1@example.com", "password": "supersecret123"},
    )
    assert r.status_code == 200
    cookie2 = r.cookies.get("clh_session")
    assert cookie2 and cookie2 != cookie1

    # 5. Old cookie must now be rejected
    client.cookies.set("clh_session", cookie1)
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401

    # 6. New cookie works
    client.cookies.set("clh_session", cookie2)
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "supersecret123",
            "first_name": "Bob",
            "last_name": "M",
        },
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "nope-nope"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient):
    payload = {
        "email": "dup@example.com",
        "password": "supersecret123",
        "first_name": "A",
        "last_name": "B",
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_student_cannot_list_users(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "student-perm@example.com",
            "password": "supersecret123",
            "first_name": "A",
            "last_name": "B",
        },
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "student-perm@example.com", "password": "supersecret123"},
    )
    r = await client.get("/api/v1/users")
    assert r.status_code == 403