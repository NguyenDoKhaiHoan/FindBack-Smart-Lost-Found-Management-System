"""
Central database model registry for FindBack.
Imports all models to register them on Base.metadata for Alembic migrations and runtime.
"""
from app.db.base import Base
from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.models.audit_log import AuditLog
from app.modules.posts.models.category import Category
from app.modules.posts.models.post import Post
from app.modules.posts.models.post_image import PostImage

__all__ = [
    "Base",
    "User",
    "Notification",
    "AuditLog",
    "Category",
    "Post",
    "PostImage",
]
