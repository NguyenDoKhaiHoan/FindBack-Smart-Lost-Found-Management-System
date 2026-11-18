import pytest
from pydantic import ValidationError

from app.modules.identity.schemas import (
    LoginRequest,
    RegisterRequest,
    UserRead,
    UserUpdate,
)


def test_register_normalizes_name_and_checks_password_strength() -> None:
    request = RegisterRequest(
        email="person@example.com",
        password="StrongPass1!",
        full_name="  Morgan Lee  ",
    )
    assert request.full_name == "Morgan Lee"

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="person@example.com",
            password="weakpass1",
            full_name="Morgan Lee",
        )
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="invalid-email",
            password="StrongPass1!",
            full_name="Morgan Lee",
        )


def test_login_accepts_existing_passwords_without_signup_policy() -> None:
    request = LoginRequest(email="person@example.com", password="legacy")
    assert request.password == "legacy"
    with pytest.raises(ValidationError):
        LoginRequest(email="person@example.com", password="a" * 73)


def test_user_read_excludes_password_fields() -> None:
    user = UserRead(
        id=1,
        email="person@example.com",
        full_name="Morgan Lee",
        role="user",
        created_at="2026-01-01T00:00:00Z",
        password="secret",
        password_hash="hash",
    )

    assert "password" not in UserRead.model_fields
    assert "password_hash" not in UserRead.model_fields
    assert "password" not in user.model_dump()
    assert "password_hash" not in user.model_dump()


def test_user_update_accepts_profile_fields_only() -> None:
    request = UserUpdate(full_name="Morgan Lee", phone="123456")
    assert request.phone == "123456"

    for invalid_patch in ({}, {"email": "new@example.com"}):
        with pytest.raises(ValidationError):
            UserUpdate(**invalid_patch)
