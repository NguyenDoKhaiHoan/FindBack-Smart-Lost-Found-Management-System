from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.modules.claims_returns.models.claim import AuditLog, Claim, ClaimEvidence, OutboxEvent
from app.modules.claims_returns.repositories.claims import ClaimRepository
from app.modules.identity.models.user import User

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def require_postgres(world):
    if world.engine.dialect.name != "postgresql":
        pytest.skip("Run with --postgres and TEST_DATABASE_URL")


def test_two_concurrent_creates_commit_exactly_one_complete_claim(world):
    barrier = Barrier(2)

    def send():
        barrier.wait(timeout=10)
        return world.client.post("/api/v1/claims", json=world.body(), headers=world.auth())

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: send(), range(2)))
    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"]["code"] == "DUPLICATE_ACTIVE_CLAIM"
    with world.factory() as session:
        for model in (Claim, ClaimEvidence, AuditLog, OutboxEvent):
            assert session.scalar(select(func.count()).select_from(model)) == 1


def test_database_unique_violation_is_mapped_by_constraint_name(world, monkeypatch):
    world.add_claim()
    # Simulate a writer outside the normal Post lock protocol bypassing the initial read.
    monkeypatch.setattr(ClaimRepository, "has_active", lambda *args: False)
    response = world.client.post("/api/v1/claims", json=world.body(), headers=world.auth())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_ACTIVE_CLAIM"
    with world.factory() as session:
        assert session.scalar(select(func.count()).select_from(Claim)) == 1


def test_real_foreign_keys_reject_nonexistent_user_and_post(world):
    for field in ("claimant_id", "found_post_id"):
        with world.factory() as session:
            values = {"claimant_id": world.ids["claimant"], "found_post_id": world.ids["found"]}
            values[field] = uuid4()
            session.add(Claim(**values))
            with pytest.raises(IntegrityError) as error:
                session.flush()
            assert error.value.orig.sqlstate == "23503"
            session.rollback()


def test_unrecognized_database_integrity_error_is_500_and_private(world, caplog):
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT") and "claim_evidence" in statement:
            raise IntegrityError(statement, parameters, RuntimeError("PRIVATE-EVIDENCE-ERROR"))

    event.listen(world.engine, "before_cursor_execute", fail)
    try:
        response = world.client.post("/api/v1/claims", json=world.body(), headers=world.auth())
    finally:
        event.remove(world.engine, "before_cursor_execute", fail)
    assert response.status_code == 500
    assert "PRIVATE-EVIDENCE-ERROR" not in response.text + caplog.text
    with world.factory() as session:
        for model in (Claim, ClaimEvidence, AuditLog, OutboxEvent):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_deleted_user_token_is_unauthenticated(world):
    with world.factory() as session:
        session.delete(session.get(User, world.ids["admin"]))
        session.commit()
    response = world.client.get("/api/v1/claims/me", headers=world.auth("admin"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
