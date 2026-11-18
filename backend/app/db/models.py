"""Import all mappings for migrations and application startup."""

from app.modules.claims_returns.models.claim import (  # noqa: F401
    AuditLog,
    Claim,
    ClaimEvidence,
    OutboxEvent,
    ReturnRecord,
)
from app.modules.identity.models.user import RefreshToken, RevokedToken, User  # noqa: F401
from app.modules.matching.models.generation import MatchGeneration, MatchResult  # noqa: F401
from app.modules.notifications_admin.models.notification import Notification  # noqa: F401
from app.modules.notifications_admin.models.report import ModerationAudit, Report  # noqa: F401
from app.modules.posts.models.post import Category, Post, PostImage  # noqa: F401
