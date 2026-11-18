from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.modules.identity.security import (
    create_access_token,
    get_user_id_from_token,
    hash_password,
    verify_password_and_update,
)


def test_password_hash_verifies_only_the_original_password() -> None:
    password = "StrongPass1!"
    hashed_password = hash_password(password)

    assert hashed_password != password
    assert hashed_password.startswith("$2")
    assert verify_password_and_update(password, hashed_password) == (True, None)
    assert verify_password_and_update("wrong-password", hashed_password) == (
        False,
        None,
    )


def test_access_token_encodes_user_id_and_expiry(jwt_secret: str) -> None:
    token = create_access_token(42)
    payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])

    assert payload["sub"] == "42"
    assert payload["iat"] <= datetime.now(timezone.utc).timestamp()
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()
    assert get_user_id_from_token(token) == 42


def test_token_decoder_rejects_wrong_signature_and_expired_token(
    jwt_secret: str,
) -> None:
    wrong_signature_token = jwt.encode(
        {
            "sub": "42",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "different-secret-key-that-is-also-over-32-characters",
        algorithm="HS256",
    )
    expired_token = jwt.encode(
        {
            "sub": "42",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        jwt_secret,
        algorithm="HS256",
    )

    for token in (wrong_signature_token, expired_token):
        with pytest.raises(HTTPException) as raised:
            get_user_id_from_token(token)
        assert raised.value.status_code == 401
