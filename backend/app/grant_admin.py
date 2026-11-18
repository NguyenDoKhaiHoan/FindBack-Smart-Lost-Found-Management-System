"""Grant the admin role to a registered user from the server command line."""

import argparse

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import make_engine, make_session_factory
from app.modules.identity.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email of an active, registered account")
    email = parser.parse_args().email.strip().casefold()
    engine = make_engine(Settings())
    try:
        with make_session_factory(engine).begin() as session:
            user = session.scalar(select(User).where(User.email == email).with_for_update())
            if user is None or not user.is_active or user.password_hash is None:
                parser.exit(1, "No active registered account matches this email.\n")
            if user.role != "ADMIN":
                user.role = "ADMIN"
                user.token_version += 1
    finally:
        engine.dispose()
    print("Administrator access is set. Sign in again to receive a new access token.")


if __name__ == "__main__":
    main()
