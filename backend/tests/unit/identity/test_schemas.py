import unittest

from pydantic import ValidationError

from app.modules.identity.schemas import (
    LoginRequest,
    RegisterRequest,
    UserRead,
    UserUpdate,
)


class IdentitySchemaTests(unittest.TestCase):
    def test_register_normalizes_name_and_checks_password_strength(self) -> None:
        request = RegisterRequest(
            email="person@example.com",
            password="StrongPass1!",
            full_name="  Morgan Lee  ",
        )
        self.assertEqual(request.full_name, "Morgan Lee")

        with self.assertRaises(ValidationError):
            RegisterRequest(
                email="person@example.com",
                password="weakpass1",
                full_name="Morgan Lee",
            )
        with self.assertRaises(ValidationError):
            RegisterRequest(
                email="invalid-email",
                password="StrongPass1!",
                full_name="Morgan Lee",
            )

    def test_login_accepts_existing_passwords_without_signup_policy(self) -> None:
        request = LoginRequest(email="person@example.com", password="legacy")
        self.assertEqual(request.password, "legacy")

    def test_user_read_excludes_password_fields(self) -> None:
        user = UserRead(
            id=1,
            email="person@example.com",
            full_name="Morgan Lee",
            role="user",
            created_at="2026-01-01T00:00:00Z",
            password="secret",
            password_hash="hash",
        )

        self.assertNotIn("password", UserRead.model_fields)
        self.assertNotIn("password_hash", UserRead.model_fields)
        self.assertNotIn("password", user.model_dump())
        self.assertNotIn("password_hash", user.model_dump())

    def test_user_update_accepts_profile_fields_only(self) -> None:
        request = UserUpdate(full_name="Morgan Lee", phone="123456")
        self.assertEqual(request.phone, "123456")

        for invalid_patch in ({}, {"email": "new@example.com"}):
            with self.subTest(patch=invalid_patch):
                with self.assertRaises(ValidationError):
                    UserUpdate(**invalid_patch)


if __name__ == "__main__":
    unittest.main()
