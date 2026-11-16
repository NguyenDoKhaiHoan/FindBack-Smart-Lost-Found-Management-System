import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.main import app
from app.modules.identity.models.user import User
from app.modules.identity.routers.auth import login, register
from app.modules.identity.routers.dependencies import get_current_user
from app.modules.identity.routers.users import read_current_user, update_current_user
from app.modules.identity.schemas import LoginRequest, RegisterRequest, UserUpdate


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

        self.assertEqual(user.full_name, "Morgan Lee")
        self.assertNotEqual(user.password_hash, payload.password)
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
            self.assertEqual(read_current_user(current_user).email, "person@example.com")

            updated_user = update_current_user(
                UserUpdate(full_name="Morgan L.", phone="123456"),
                current_user,
                self.db,
            )
        self.assertEqual(updated_user.full_name, "Morgan L.")
        self.assertEqual(updated_user.phone, "123456")

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

    def test_identity_routes_are_in_openapi(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/auth/register", paths)
        self.assertIn("/api/v1/auth/login", paths)
        self.assertIn("/api/v1/users/me", paths)
        self.assertIn("get", paths["/api/v1/users/me"])
        self.assertIn("patch", paths["/api/v1/users/me"])
