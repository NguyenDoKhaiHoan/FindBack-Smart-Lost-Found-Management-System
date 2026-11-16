import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import AuditLog, Claim, OutboxEvent, ReturnRecord
from app.modules.claims_returns.repositories.claims import ClaimRepository
from app.modules.claims_returns.repositories.returns import ReturnRepository
from app.modules.notifications_admin.schemas.claim_events import ClaimNotificationEvent
from app.modules.posts.models.post import Post
from tests.api.test_claims import assert_error, assert_schema
from tests.decision_helpers import alter_post, legacy_return, patch, pending, ready, snapshot


def assert_recorded(world, claim_id, action, version, recipient, actor):
    with world.factory() as session:
        rows = list(session.scalars(select(OutboxEvent).where(OutboxEvent.type == action)))
        assert len(rows) == 1
        payload = rows[0].payload
        parsed = ClaimNotificationEvent.model_validate(payload)
        assert parsed.event_id == rows[0].event_id and parsed.type == action
        assert parsed.claim_id == claim_id and parsed.found_post_id == world.ids["found"]
        assert parsed.version == version and parsed.recipient_id == world.ids[recipient]
        assert "Fictional" not in json.dumps(payload)
        audit = session.scalar(select(AuditLog).where(AuditLog.action == action))
        assert audit.actor_id == world.ids[actor] and audit.claim_id == claim_id
        assert audit.previous_version == version - 1 and audit.version == version
        assert audit.occurred_at == parsed.occurred_at


def test_approve_preserves_post_and_competing_claim(world):
    claim_id = pending(world)
    competing = pending(world, actor="other")
    response = patch(world, claim_id, "approve")
    assert response.status_code == 200, response.text
    assert_schema(response, "ClaimSummary")
    data = response.json()
    assert data["status"] == "APPROVED" and data["version"] == 2
    assert data["decided_by"] == str(world.ids["owner"]) and data["decided_at"]
    assert data["rejection_reason"] is None and data["return_summary"] is None
    assert "Fictional secret" not in response.text
    with world.factory() as session:
        assert session.get(Post, world.ids["found"]).status == "OPEN"
        assert session.get(Claim, competing).status == "PENDING"
        assert session.scalar(select(func.count()).select_from(ReturnRecord)) == 0
    assert_recorded(world, claim_id, "claim.approved", 2, "claimant", "owner")


def test_reject_trims_reason_and_does_not_close_post(world, caplog):
    claim_id = pending(world)
    response = patch(world, claim_id, "reject")
    assert response.status_code == 200, response.text
    assert_schema(response, "ClaimSummary")
    assert response.json()["status"] == "REJECTED" and response.json()["version"] == 2
    assert response.json()["rejection_reason"] == "Fictional private rejection reason"
    assert "Fictional private rejection reason" not in caplog.text
    with world.factory() as session:
        assert session.get(Post, world.ids["found"]).status == "OPEN"
        assert session.scalar(select(func.count()).select_from(ReturnRecord)) == 0
    assert_recorded(world, claim_id, "claim.rejected", 2, "claimant", "owner")


def test_complete_updates_claim_return_post_and_actors_at_same_time(world):
    claim_id, version = ready(world)
    response = patch(world, claim_id, "complete", version=version)
    assert response.status_code == 200, response.text
    assert_schema(response, "ClaimSummary")
    data = response.json()
    assert data["status"] == "RETURNED" and data["version"] == version + 1
    assert data["returned_by"] == str(world.ids["claimant"])
    assert data["return_summary"]["status"] == "CONFIRMED"
    assert data["returned_at"] == data["return_summary"]["confirmed_at"]
    with world.factory() as session:
        claim = session.get(Claim, claim_id)
        record = session.scalar(select(ReturnRecord).where(ReturnRecord.claim_id == claim_id))
        post = session.get(Post, world.ids["found"])
        assert record.confirmed_by == claim.returned_by == world.ids["claimant"]
        assert record.confirmed_at == claim.returned_at == claim.updated_at == post.completed_at
        assert post.status == "CLOSED" and post.completed_claim_id == claim_id
        assert claim.decided_by == world.ids["owner"]
    assert_recorded(world, claim_id, "claim.completed", 4, "owner", "claimant")
    before = snapshot(world)
    assert_error(patch(world, claim_id, "complete", version=version), 409, "CLAIM_STATE_CONFLICT")
    assert snapshot(world) == before


@pytest.mark.parametrize(
    "action,actor,status,code",
    [
        (action, actor, status, code)
        for action in ("approve", "reject", "complete")
        for actor, status, code in [
            ("other", 404, "CLAIM_NOT_FOUND"),
            ("admin", 404, "CLAIM_NOT_FOUND"),
            ("locked", 403, "ACCOUNT_FORBIDDEN"),
            ("owner" if action == "complete" else "claimant", 403, "CLAIM_ACTION_FORBIDDEN"),
        ]
    ],
)
def test_roles_do_not_inherit_unrelated_or_self_approval_rights(world, action, actor, status, code):
    claim_id = pending(world)
    before = snapshot(world)
    assert_error(patch(world, claim_id, action, actor=actor), status, code)
    assert snapshot(world) == before


@pytest.mark.parametrize("action", ["approve", "reject", "complete"])
def test_patch_requires_auth_and_hides_missing_claim(world, action):
    claim_id = pending(world)
    response = world.client.patch(
        f"/api/v1/claims/{claim_id}/{action}", json={"expected_version": 1}
    )
    assert_error(response, 401, "UNAUTHENTICATED")
    assert_error(patch(world, uuid4(), action), 404, "CLAIM_NOT_FOUND")


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_legacy_self_claim_never_self_decides(world, action):
    claim_id = world.add_claim(post="own")
    before = snapshot(world)
    assert_error(patch(world, claim_id, action, actor="claimant"), 403, "CLAIM_ACTION_FORBIDDEN")
    assert snapshot(world) == before


@pytest.mark.parametrize(
    "action,state",
    [
        (action, state)
        for action in ("approve", "reject", "complete")
        for state in ("PENDING", "APPROVED", "REJECTED", "RETURNED")
        if state != ("APPROVED" if action == "complete" else "PENDING")
    ],
)
def test_illegal_state_wins_over_stale_version_and_changes_nothing(world, action, state):
    claim_id = world.add_claim(status=state)
    before = snapshot(world)
    assert_error(patch(world, claim_id, action, version=999), 409, "CLAIM_STATE_CONFLICT")
    assert snapshot(world) == before


@pytest.mark.parametrize("action", ["approve", "reject", "complete"])
def test_stale_version_changes_nothing(world, action):
    claim_id = world.add_claim(status="APPROVED" if action == "complete" else "PENDING")
    before = snapshot(world)
    assert_error(patch(world, claim_id, action, version=999), 409, "CLAIM_VERSION_CONFLICT")
    assert snapshot(world) == before


@pytest.mark.parametrize("action", ["approve", "reject", "complete"])
@pytest.mark.parametrize("version", [0, -1, 1.5, "1", True, None])
def test_strict_expected_version(world, action, version):
    claim_id = world.add_claim()
    assert_error(patch(world, claim_id, action, version=version), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("reason", ["", " \t\n ", "x" * 1001, None, 123])
def test_rejection_reason_validation(world, reason):
    claim_id = world.add_claim()
    assert_error(patch(world, claim_id, "reject", reason=reason), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("confirmation", [False, "true", 1, None])
def test_complete_requires_boolean_true(world, confirmation):
    claim_id = world.add_claim(status="APPROVED")
    assert_error(
        patch(world, claim_id, "complete", receipt_confirmed=confirmation), 422, "VALIDATION_ERROR"
    )


@pytest.mark.parametrize("action", ["approve", "reject", "complete"])
@pytest.mark.parametrize("field", ["decided_by", "returned_by", "return_id", "status", "role"])
def test_patch_mass_assignment_is_rejected(world, action, field):
    assert_error(
        patch(world, uuid4(), action, **{field: "Fictional private input"}), 422, "VALIDATION_ERROR"
    )


@pytest.mark.parametrize("action", ["approve", "reject", "complete"])
def test_patch_rejects_bad_path_missing_body_and_extra_query(world, action):
    assert_error(patch(world, "bad", action), 422, "VALIDATION_ERROR")
    path = f"/api/v1/claims/{uuid4()}/{action}"
    assert_error(world.client.patch(path, json={}, headers=world.auth()), 422, "VALIDATION_ERROR")
    body = (
        {"expected_version": 1, "reason": "reason"}
        if action == "reject"
        else {"expected_version": 1}
    )
    if action == "complete":
        body["receipt_confirmed"] = True
    assert_error(
        world.client.patch(path + "?user_id=any", json=body, headers=world.auth()),
        422,
        "VALIDATION_ERROR",
    )


def test_approve_requires_existing_valid_text_evidence(world):
    claim_id = world.add_claim()
    before = snapshot(world)
    assert_error(patch(world, claim_id, "approve"), 422, "EVIDENCE_REQUIRED")
    assert snapshot(world) == before


@pytest.mark.parametrize(
    "post_changes",
    [
        {"status": "CLOSED"},
        {"is_hidden": True},
        {"deleted_at": utcnow()},
        {"type": "LOST"},
    ],
)
def test_approve_checks_post_state(world, post_changes):
    claim_id = pending(world)
    alter_post(world, **post_changes)
    before = snapshot(world)
    assert_error(patch(world, claim_id, "approve"), 409, "POST_NOT_CLAIMABLE")
    assert snapshot(world) == before


@pytest.mark.parametrize("winner_state", ["APPROVED", "RETURNED"])
def test_approve_does_not_replace_winner(world, winner_state):
    claim_id = pending(world)
    winner_id = world.add_claim(claimant="other", status=winner_state)
    before = snapshot(world)
    response = patch(world, claim_id, "approve")
    assert_error(response, 409, "POST_ALREADY_ASSIGNED")
    assert str(winner_id) not in response.text
    assert snapshot(world) == before


@pytest.mark.parametrize("post_changes", [{"status": "CLOSED"}, {"is_hidden": True}])
def test_reject_allows_resolving_pending_claims_on_unavailable_posts(world, post_changes):
    claim_id = pending(world)
    alter_post(world, **post_changes)
    assert patch(world, claim_id, "reject").status_code == 200


def test_reject_pending_competitor_after_winner_is_chosen(world):
    claim_id = pending(world)
    world.add_claim(claimant="other", status="APPROVED")
    assert patch(world, claim_id, "reject").status_code == 200


@pytest.mark.parametrize("state", [None, "ARRANGED", "CONFIRMED"])
def test_complete_never_invents_handover(world, state):
    claim_id = world.add_claim(status="APPROVED")
    if state:
        legacy_return(world, claim_id, state)
    before = snapshot(world)
    assert_error(patch(world, claim_id, "complete"), 409, "RETURN_NOT_READY")
    assert snapshot(world) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"handed_over_at": None},
        {"handed_over_at": utcnow() - timedelta(days=1)},
        {"handed_over_at": utcnow() + timedelta(days=1)},
        {"confirmed_at": utcnow()},
    ],
)
def test_complete_rejects_inconsistent_handover_metadata(world, changes):
    claim_id, version = ready(world)
    with world.factory() as session:
        record = session.scalar(select(ReturnRecord))
        for key, value in changes.items():
            setattr(record, key, value)
        session.commit()
    before = snapshot(world)
    assert_error(patch(world, claim_id, "complete", version=version), 409, "RETURN_NOT_READY")
    assert snapshot(world) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "CLOSED"},
        {"is_hidden": True},
        {"deleted_at": utcnow()},
        {"type": "LOST"},
    ],
)
def test_complete_post_conflict_rolls_back_return_confirmation(world, changes):
    claim_id, version = ready(world)
    alter_post(world, **changes)
    before = snapshot(world)
    assert_error(patch(world, claim_id, "complete", version=version), 409, "POST_STATE_CONFLICT")
    assert snapshot(world) == before


def test_complete_preserves_existing_consistent_post_completion_marker(world):
    claim_id, version = ready(world)
    completed_at = utcnow() - timedelta(seconds=1)
    alter_post(world, status="CLOSED", completed_claim_id=claim_id, completed_at=completed_at)
    response = patch(world, claim_id, "complete", version=version)
    assert response.status_code == 200, response.text
    with world.factory() as session:
        assert session.get(Post, world.ids["found"]).completed_at == completed_at


@pytest.mark.parametrize(
    "action,table",
    [
        ("approve", "claims"),
        ("approve", "audit_logs"),
        ("approve", "outbox_events"),
        ("reject", "audit_logs"),
        ("reject", "outbox_events"),
        ("complete", "returns"),
        ("complete", "posts"),
        ("complete", "claims"),
        ("complete", "audit_logs"),
        ("complete", "outbox_events"),
    ],
)
def test_mutation_failures_roll_back_every_table_without_leaking_secrets(
    world, action, table, caplog
):
    claim_id, version = ready(world) if action == "complete" else (pending(world), 1)
    before = snapshot(world)

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith(("UPDATE", "INSERT")) and f".{table} " in statement:
            raise SQLAlchemyError("Fictional private storage exception")

    event.listen(world.engine, "before_cursor_execute", fail)
    try:
        response = patch(world, claim_id, action, version=version)
    finally:
        event.remove(world.engine, "before_cursor_execute", fail)
    assert response.status_code == 500, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert "Fictional" not in response.text + caplog.text
    assert snapshot(world) == before


def test_claim_version_compare_and_set_failure_rolls_back_return_and_post(world, monkeypatch):
    claim_id, version = ready(world)
    before = snapshot(world)
    monkeypatch.setattr(ClaimRepository, "transition", lambda *args, **kwargs: False)
    assert_error(patch(world, claim_id, "complete", version=version), 409, "CLAIM_VERSION_CONFLICT")
    assert snapshot(world) == before


def test_return_compare_and_set_failure_changes_nothing(world, monkeypatch):
    claim_id, version = ready(world)
    before = snapshot(world)
    monkeypatch.setattr(ReturnRepository, "confirm", lambda *args: False)
    assert_error(patch(world, claim_id, "complete", version=version), 409, "RETURN_NOT_READY")
    assert snapshot(world) == before


def test_complete_cannot_overwrite_another_claims_post_marker(world):
    claim_id, version = ready(world)
    another_claim = world.add_claim(post="second")
    alter_post(world, status="CLOSED", completed_claim_id=another_claim, completed_at=utcnow())
    before = snapshot(world)
    assert_error(patch(world, claim_id, "complete", version=version), 409, "POST_STATE_CONFLICT")
    assert snapshot(world) == before
