from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def create(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    return user


def update_profile(db: Session, user: User, changes: dict[str, str | None]) -> User:
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    return user
