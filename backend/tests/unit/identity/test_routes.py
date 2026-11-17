import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.modules.identity.models.user import User
from app.modules.identity.routers.auth import login, register
from app.modules.identity.routers.dependencies import get_current_user
from app.modules.identity.routers.users import read_current_user, update_current_user
from app.modules.identity.schemas import (
    LoginRequest,
    RegisterRequest,
    UserRead,
    UserUpdate,
)
from app.modules.identity.security import get_user_id_from_token
from app.modules.identity.services.auth_service import authenticate_user
from app.modules.identity.services.user_service import (
    get_user_profile,
    update_user_profile,
)

legacy_password_context = CryptContext(schemes=["argon2"])


class IdentityRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def setUp(self) -> None:
        self.db = Session(self.engine)
        self.db.execute(delete(User))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_register_persists_user_and_rejects_duplicate_email(self) -> None:
        payload = RegisterRequest(
            email="person@example.com",
            password="StrongPass1!",
            full_name="Morgan Lee",
        )
        user = register(payload, self.db)
        stored_user = self.db.scalar(
            select(User).where(User.email == "person@example.com")
        )

        self.assertEqual(user.full_name, "Morgan Lee")
        self.assertNotIn("password_hash", UserRead.model_fields)
        assert stored_user is not None
        self.assertNotEqual(stored_user.password_hash, payload.password)
        with self.assertRaises(HTTPException) as raised:
            register(payload, self.db)
        self.assertEqual(raised.exception.status_code, 409)

    def test_login_token_authenticates_and_updates_current_user(self) -> None:
        register(
            RegisterRequest(
                email="person@example.com",
                password="StrongPass1!",
                full_name="Morgan Lee",
            ),
            self.db,
        )

        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-" * 4}):
            token = login(
                LoginRequest(
                    email="person@example.com",
                    password="StrongPass1!",
                ),
                self.db,
            )
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token.access_token,
            )
            current_user = get_current_user(credentials, self.db)
            profile = read_current_user(current_user)
            self.assertEqual(profile.email, "person@example.com")
            self.assertNotIn("password_hash", profile.model_dump())
            self.assertNotIn("password_hash", UserRead.model_fields)

            updated_user = update_current_user(
                UserUpdate(
                    full_name="Morgan L.",
                    phone="123456",
                    avatar_url="https://example.com/avatar.png",
                ),
                current_user,
                self.db,
            )
        self.assertEqual(updated_user.full_name, "Morgan L.")
        self.assertEqual(updated_user.phone, "123456")
        self.assertEqual(str(updated_user.avatar_url), "https://example.com/avatar.png")

    def test_profile_service_reads_and_clears_optional_fields(self) -> None:
        user = register(
            RegisterRequest(
                email="profile@example.com",
                password="StrongPass1!",
                full_name="Profile User",
            ),
            self.db,
        )
        stored_user = self.db.scalar(
            select(User).where(User.email == "profile@example.com")
        )
        assert stored_user is not None
        self.assertEqual(get_user_profile(stored_user).id, user.id)

        updated = update_user_profile(
            self.db,
            stored_user,
            UserUpdate(phone=None, avatar_url=None),
        )
        self.assertIsNone(updated.phone)
        self.assertIsNone(updated.avatar_url)
        self.assertNotIn("password_hash", updated.model_dump())

    def test_login_rejects_invalid_password(self) -> None:
        register(
            RegisterRequest(
                email="person@example.com",
                password="StrongPass1!",
                full_name="Morgan Lee",
            ),
            self.db,
        )
        with self.assertRaises(HTTPException) as raised:
            login(
                LoginRequest(email="person@example.com", password="wrong"),
                self.db,
            )
        self.assertEqual(raised.exception.status_code, 401)

    def test_legacy_argon2_hash_is_upgraded_after_successful_login(self) -> None:
        user = User(
            email="legacy@example.com",
            full_name="Legacy User",
            password_hash=legacy_password_context.hash("StrongPass1!"),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret-" * 4}):
            token = authenticate_user(
                self.db,
                LoginRequest(
                    email="legacy@example.com",
                    password="StrongPass1!",
                ),
            )

        self.assertEqual(token.token_type, "bearer")
        self.assertTrue(user.password_hash.startswith("$2b$"))

    def test_missing_invalid_and_expired_tokens_are_rejected(self) -> None:
        with self.assertRaises(HTTPException) as missing:
            get_current_user(None, self.db)
        self.assertEqual(missing.exception.status_code, 401)

        secret = "test-secret-" * 4
        expired_token = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            secret,
            algorithm="HS256",
        )
        with patch.dict(os.environ, {"JWT_SECRET_KEY": secret}):
            for token in ("not-a-jwt", expired_token):
                with self.subTest(token=token):
                    with self.assertRaises(HTTPException) as raised:
                        get_user_id_from_token(token)
                    self.assertEqual(raised.exception.status_code, 401)

    def test_identity_routes_are_in_openapi(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/auth/register", paths)
        self.assertIn("/api/v1/auth/login", paths)
        self.assertIn("/api/v1/users/me", paths)
        self.assertIn("get", paths["/api/v1/users/me"])
        self.assertIn("patch", paths["/api/v1/users/me"])
