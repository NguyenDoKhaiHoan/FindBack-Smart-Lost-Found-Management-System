from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import psycopg
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError

from app.modules.claims_returns.models.claim import AuditLog, Claim, OutboxEvent, ReturnRecord
from app.modules.posts.models.post import Post
from tests.api.test_claims import assert_error
from tests.decision_helpers import patch, pending, ready, snapshot


@pytest.mark.postgres
@pytest.mark.parametrize("race", ["two_approvals", "approve_reject", "two_completions"])
def test_waiting_competitors_serialize_on_post_and_only_one_commits(world, race):
    if world.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    if race == "two_completions":
        claim_id, version = ready(world)
        requests = [(claim_id, "complete", version)] * 2
    else:
        first = pending(world)
        second = pending(world, actor="other") if race == "two_approvals" else first
        requests = [
            (first, "approve", 1),
            (second, "reject" if race == "approve_reject" else "approve", 1),
        ]
    started = Event()
    counter_lock = Lock()
    waiting = 0

    def record(conn, cursor, statement, parameters, context, executemany):
        nonlocal waiting
        if "FOR UPDATE" in statement and ".posts" in statement:
            with counter_lock:
                waiting += 1
                if waiting >= 2:
                    started.set()

    def send(request):
        claim_id, action, version = request
        return patch(world, claim_id, action, version=version)

    with ThreadPoolExecutor(max_workers=2) as pool:
        # Hold Post first so both HTTP requests demonstrably block on the same row.
        with world.factory() as holder:
            holder.scalar(select(Post).where(Post.id == world.ids["found"]).with_for_update())
            event.listen(world.engine, "before_cursor_execute", record)
            try:
                futures = [pool.submit(send, item) for item in requests]
                assert started.wait(timeout=10), "Both requests must reach the Post lock"
                assert all(not future.done() for future in futures)
            finally:
                event.remove(world.engine, "before_cursor_execute", record)
                holder.rollback()
        responses = [future.result(timeout=15) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    expected = "POST_ALREADY_ASSIGNED" if race == "two_approvals" else "CLAIM_STATE_CONFLICT"
    assert_error(conflict, 409, expected)
    with world.factory() as session:
        if race == "two_completions":
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ReturnRecord)
                    .where(ReturnRecord.status == "CONFIRMED")
                )
                == 1
            )
            post = session.get(Post, world.ids["found"])
            claim = session.get(Claim, claim_id)
            assert post.status == "CLOSED" and post.completed_claim_id == claim_id
            assert claim.status == "RETURNED" and claim.version == version + 1
            audit_actions = ["claim.completed"]
        else:
            assert session.get(Post, world.ids["found"]).status == "OPEN"
            audit_actions = ["claim.approved", "claim.rejected"]
        for model, column in ((AuditLog, AuditLog.action), (OutboxEvent, OutboxEvent.type)):
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(column.in_(audit_actions))
                )
                == 1
            )


@pytest.mark.parametrize(
    "error_type", [psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected]
)
def test_aborted_transactions_retry_without_duplicate_audit_or_event(world, error_type):
    claim_id = pending(world)
    attempts = 0

    def fail_first_two(conn, cursor, statement, parameters, context, executemany):
        nonlocal attempts
        if statement.startswith("INSERT") and ".audit_logs " in statement:
            attempts += 1
            if attempts < 3:
                raise OperationalError(
                    statement, parameters, error_type("Fictional retry condition")
                )

    event.listen(world.engine, "before_cursor_execute", fail_first_two)
    try:
        response = patch(world, claim_id, "approve")
    finally:
        event.remove(world.engine, "before_cursor_execute", fail_first_two)
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2 and attempts == 3
    with world.factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "claim.approved")
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.type == "claim.approved")
            )
            == 1
        )


def test_transaction_retry_is_bounded_and_rollback_is_complete(world):
    claim_id, version = ready(world)
    before = snapshot(world)
    attempts = 0

    def always_fail(conn, cursor, statement, parameters, context, executemany):
        nonlocal attempts
        if statement.startswith("INSERT") and ".audit_logs " in statement:
            attempts += 1
            raise OperationalError(
                statement, parameters, psycopg.errors.SerializationFailure("retry")
            )

    event.listen(world.engine, "before_cursor_execute", always_fail)
    try:
        response = patch(world, claim_id, "complete", version=version)
    finally:
        event.remove(world.engine, "before_cursor_execute", always_fail)
    assert response.status_code == 500 and attempts == 3
    assert snapshot(world) == before


@pytest.mark.postgres
def test_notifications_event_is_visible_to_other_connections_only_after_commit(world):
    if world.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL isolation")
    claim_id = pending(world)
    visible_during_transaction = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT") and ".outbox_events " in statement:
            with world.factory() as reader:
                visible_during_transaction.append(
                    reader.scalar(
                        select(func.count())
                        .select_from(OutboxEvent)
                        .where(OutboxEvent.type == "claim.approved")
                    )
                )

    event.listen(world.engine, "after_cursor_execute", observe)
    try:
        response = patch(world, claim_id, "approve")
    finally:
        event.remove(world.engine, "after_cursor_execute", observe)
    assert response.status_code == 200
    assert visible_during_transaction == [0]
    with world.factory() as reader:
        assert (
            reader.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.type == "claim.approved")
            )
            == 1
        )
