"""Run live decision checks with fictional data; never synthesize handover in the API."""

import json
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from app.core.config import BACKEND_DIR, Settings
from app.db import models  # noqa: F401
from app.db.session import make_engine, make_session_factory, utcnow
from app.modules.claims_returns.models.claim import AuditLog, Claim, OutboxEvent, ReturnRecord
from app.modules.posts.models.post import Post


def main():
    settings = Settings()
    if settings.app_env != "development":
        raise SystemExit("Live fictional-data checks require APP_ENV=development")
    demo = json.loads((BACKEND_DIR / ".local/claims-demo.json").read_text(encoding="utf-8"))
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    post_id = uuid4()
    with factory() as session:
        session.add(Post(id=post_id, owner_id=UUID(demo["users"]["owner"]["id"]), type="FOUND"))
        session.commit()
    checks = []

    def auth(actor):
        return {"Authorization": "Bearer " + demo["users"][actor]["token"]}

    def check(name, response, expected, code=None):
        passed = response.status_code == expected
        passed = passed and response.headers.get("Cache-Control") == "no-store"
        if code:
            passed = passed and response.json().get("error", {}).get("code") == code
        checks.append({"check": name, "status": response.status_code, "passed": passed})
        if not passed:
            raise AssertionError(f"Failed {name}: HTTP {response.status_code}")

    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
        body = {
            "found_post_id": str(post_id),
            "evidence_description": "Fictional DECISIONS-DEMO secret",
        }
        claims = []
        for actor in ("claimant", "outsider"):
            response = client.post("/api/v1/claims", json=body, headers=auth(actor))
            check(f"create {actor} claim", response, 201)
            claims.append(response.json()["id"])
        winner, competitor = claims

        def send(claim_id, action, actor="owner", version=1, **extra):
            data = {"expected_version": version}
            if action == "reject":
                data["reason"] = "Fictional private rejection reason"
            if action == "complete":
                data["receipt_confirmed"] = True
            return client.patch(
                f"/api/v1/claims/{claim_id}/{action}",
                headers=auth(actor),
                json={**data, **extra},
            )

        check(
            "self approval blocked",
            send(winner, "approve", "claimant"),
            403,
            "CLAIM_ACTION_FORBIDDEN",
        )
        check(
            "unrelated actor blocked", send(winner, "approve", "outsider"), 404, "CLAIM_NOT_FOUND"
        )
        check(
            "stale decision blocked",
            send(winner, "approve", version=999),
            409,
            "CLAIM_VERSION_CONFLICT",
        )
        check("approve", send(winner, "approve"), 200)
        check("repeated approval blocked", send(winner, "approve"), 409, "CLAIM_STATE_CONFLICT")
        check(
            "competing approval blocked", send(competitor, "approve"), 409, "POST_ALREADY_ASSIGNED"
        )
        check("reject competitor", send(competitor, "reject"), 200)
        check("repeated rejection blocked", send(competitor, "reject"), 409, "CLAIM_STATE_CONFLICT")
        check(
            "owner cannot confirm receipt",
            send(winner, "complete", version=2),
            403,
            "CLAIM_ACTION_FORBIDDEN",
        )
        check(
            "missing handover blocked",
            send(winner, "complete", "claimant", 2),
            409,
            "RETURN_NOT_READY",
        )
        # Explicit fictional fixture for the Returns integration prerequisite.
        # Production must use an authorized Returns workflow; complete never creates it.
        with factory() as session:
            claim = session.get(Claim, UUID(winner))
            session.add(
                ReturnRecord(claim_id=claim.id, status="HANDED_OVER", handed_over_at=utcnow())
            )
            claim.version += 1
            claim.updated_at = utcnow()
            session.commit()
        response = send(winner, "complete", "claimant", 3)
        check("confirm real handover prerequisite", response, 200)
        assert response.json()["status"] == "RETURNED"
        assert response.json()["return_summary"]["status"] == "CONFIRMED"
        check(
            "repeated completion blocked",
            send(winner, "complete", "claimant", 3),
            409,
            "CLAIM_STATE_CONFLICT",
        )
        response = client.get(f"/api/v1/claims/{winner}", headers=auth("claimant"))
        check("detail reflects completion", response, 200)
    with factory() as session:
        claim = session.get(Claim, UUID(winner))
        record = session.scalar(select(ReturnRecord).where(ReturnRecord.claim_id == claim.id))
        post = session.get(Post, post_id)
        assert post.status == "CLOSED" and post.completed_claim_id == claim.id
        assert claim.returned_at == record.confirmed_at == post.completed_at
        assert record.confirmed_by == claim.claimant_id
        audits = list(session.scalars(select(AuditLog).where(AuditLog.found_post_id == post_id)))
        events = list(
            session.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.payload["found_post_id"].as_string() == str(post_id)
                )
            )
        )
        assert len(audits) == len(events) == 5
        assert sum(event.type == "claim.completed" for event in events) == 1
        assert all("Fictional" not in json.dumps(event.payload) for event in events)
    report = BACKEND_DIR / ".local/claims-decisions-live-checks.json"
    report.write_text(
        json.dumps(
            {
                "target": "Uvicorn + PostgreSQL local",
                "checks": checks,
                "consistent_claim_return_post": True,
                "audit_count": 5,
                "outbox_count": 5,
                "handover_fixture": "fictional development data only",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    engine.dispose()
    print(f"{len(checks)} live decision checks passed; 5 audit/outbox records. Report: {report}")


if __name__ == "__main__":
    main()
