from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.identity.models.user import User


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def create(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def save(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_profile(
    db: Session,
    user: User,
    changes: dict[str, str | None],
) -> User:
    for field, value in changes.items():
        setattr(user, field, value)

    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise
    return user
