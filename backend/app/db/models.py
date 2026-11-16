"""Import all mappings for migrations and application startup."""

from app.modules.claims_returns.models.claim import (  # noqa: F401
    AuditLog,
    Claim,
    ClaimEvidence,
    OutboxEvent,
    ReturnRecord,
)
from app.modules.identity.models.user import RevokedToken, User  # noqa: F401
from app.modules.posts.models.post import Post  # noqa: F401
