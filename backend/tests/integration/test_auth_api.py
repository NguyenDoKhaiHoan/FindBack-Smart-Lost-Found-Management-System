from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

PASSWORD = "StrongPass1!"


def register_user(
    client: TestClient,
    email: str = "person@example.com",
    full_name: str = "Morgan Lee",
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": full_name,
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(client: TestClient, email: str = "person@example.com") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_register_succeeds_and_does_not_expose_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "person@example.com",
            "password": PASSWORD,
            "full_name": "Morgan Lee",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "person@example.com"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "person@example.com",
            "password": PASSWORD,
            "full_name": "Another User",
        },
    )

    assert response.status_code == 409


def test_login_accepts_correct_credentials(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "person@example.com", "password": "WrongPass1!"},
        {"email": "missing@example.com", "password": PASSWORD},
    ],
)
def test_login_rejects_incorrect_credentials(
    client: TestClient, credentials: dict
) -> None:
    register_user(client)

    response = client.post("/api/v1/auth/login", json=credentials)

    assert response.status_code == 401


def test_get_and_patch_current_profile_with_valid_token(
    client: TestClient,
) -> None:
    register_user(client)
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    profile_response = client.get("/api/v1/users/me", headers=headers)
    update_response = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={
            "full_name": "Morgan L.",
            "phone": "0900000000",
            "avatar_url": "https://example.com/avatar.png",
        },
    )

    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == "person@example.com"
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Morgan L."
    assert update_response.json()["phone"] == "0900000000"
    assert update_response.json()["avatar_url"] == "https://example.com/avatar.png"
    assert "password_hash" not in update_response.json()


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/v1/users/me", None),
        ("patch", "/api/v1/users/me", {"full_name": "Changed Name"}),
    ],
)
@pytest.mark.parametrize("token_kind", ["wrong_signature", "expired"])
def test_profile_endpoints_reject_invalid_or_expired_tokens(
    client: TestClient,
    jwt_secret: str,
    method: str,
    path: str,
    body: dict | None,
    token_kind: str,
) -> None:
    if token_kind == "wrong_signature":
        secret = "different-secret-key-that-is-also-over-32-characters"
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    else:
        secret = jwt_secret
        expiry = datetime.now(timezone.utc) - timedelta(minutes=1)

    token = jwt.encode(
        {"sub": "1", "exp": expiry},
        secret,
        algorithm="HS256",
    )
    response = client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )

    assert response.status_code == 401


def test_profile_update_cannot_change_role_or_another_users_profile(
    client: TestClient,
) -> None:
    register_user(client, "first@example.com", "First User")
    register_user(client, "second@example.com", "Second User")
    first_token = login_user(client, "first@example.com")
    second_token = login_user(client, "second@example.com")

    forbidden_update = client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {first_token}"},
        json={"role": "admin"},
    )
    own_profile_update = client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {first_token}"},
        json={"full_name": "Updated First User"},
    )
    second_profile = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert forbidden_update.status_code == 422
    assert own_profile_update.status_code == 200
    assert own_profile_update.json()["full_name"] == "Updated First User"
    assert second_profile.status_code == 200
    assert second_profile.json()["full_name"] == "Second User"
