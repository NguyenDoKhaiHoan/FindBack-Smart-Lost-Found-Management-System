from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import (
    AuditLog,
    Claim,
    ClaimEvidence,
    OutboxEvent,
    ReturnRecord,
)
from app.modules.posts.models.post import Post


def patch(world, claim_id, action, *, actor=None, version=1, **extra):
    actor = actor or ("claimant" if action == "complete" else "owner")
    body = {"expected_version": version}
    if action == "reject":
        body["reason"] = "  Fictional private rejection reason  "
    if action == "complete":
        body["receipt_confirmed"] = True
    return world.client.patch(
        f"/api/v1/claims/{claim_id}/{action}",
        json={**body, **extra},
        headers=world.auth(actor),
    )


def pending(world, *, actor="claimant", post="found"):
    response = world.client.post("/api/v1/claims", json=world.body(post), headers=world.auth(actor))
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


def ready(world):
    claim_id = pending(world)
    response = patch(world, claim_id, "approve")
    assert response.status_code == 200, response.text
    with world.factory() as session:
        session.add(
            ReturnRecord(
                claim_id=claim_id,
                status="HANDED_OVER",
                handed_over_at=utcnow(),
            )
        )
        # Represents the Returns integration changing handover state, not the complete API.
        claim = session.get(Claim, claim_id)
        claim.version += 1
        claim.updated_at = utcnow()
        session.commit()
    return claim_id, 3


def snapshot(world):
    with world.factory() as session:
        return {
            model.__tablename__: list(
                session.execute(
                    select(model.__table__).order_by(*model.__table__.primary_key.columns)
                ).mappings()
            )
            for model in (Post, Claim, ClaimEvidence, ReturnRecord, AuditLog, OutboxEvent)
        }


def alter_post(world, **values):
    with world.factory() as session:
        post = session.get(Post, world.ids["found"])
        for key, value in values.items():
            setattr(post, key, value)
        session.commit()


def legacy_return(world, claim_id, status):
    with world.factory() as session:
        session.add(
            ReturnRecord(
                claim_id=claim_id,
                status=status,
                handed_over_at=utcnow() - timedelta(minutes=1) if status != "ARRANGED" else None,
                confirmed_at=utcnow() if status == "CONFIRMED" else None,
                confirmed_by=world.ids["claimant"] if status == "CONFIRMED" else None,
            )
        )
        session.commit()
