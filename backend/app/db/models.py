"""
Central database model registry for FindBack.
Imports all models to register them on Base.metadata for Alembic migrations and runtime.
"""
from app.db.base import Base
from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.notification import Notification

__all__ = ["Base", "User", "Notification"]
