import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import (
    AuditLog,
    Claim,
    ClaimEvidence,
    OutboxEvent,
    ReturnRecord,
)
from app.modules.identity.models.user import RevokedToken, User

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[3] / "docs/api/claims.openapi.json").read_text(
        encoding="utf-8"
    )
)


def assert_schema(response, name):
    schema = {"$ref": f"#/components/schemas/{name}", "components": CONTRACT["components"]}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(response.json())
    assert response.headers["Cache-Control"] == "no-store"


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert_schema(response, "ApiError")
    assert "Fictional secret" not in response.text
    if status == 401:
        assert response.headers["WWW-Authenticate"] == "Bearer"


def create(world, actor="claimant", **body):
    return world.client.post("/api/v1/claims", json=world.body(**body), headers=world.auth(actor))


def test_create_is_pending_atomic_and_private(world):
    response = create(world)
    assert response.status_code == 201, response.text
    assert_schema(response, "ClaimSummary")
    body = response.json()
    assert body["claimant_id"] == str(world.ids["claimant"])
    assert body["found_post_id"] == str(world.ids["found"])
    assert body["status"] == "PENDING" and body["version"] == 1
    assert response.headers["Location"] == f"/api/v1/claims/{body['id']}"
    assert "evidence" not in body and "DEMO-123" not in response.text
    with world.factory() as session:
        evidence = session.scalar(select(ClaimEvidence))
        assert evidence.private_content == "Fictional secret marking DEMO-123"
        assert session.scalar(select(func.count()).select_from(Claim)) == 1
        audit = session.scalar(select(AuditLog))
        assert audit.actor_id == world.ids["claimant"] and audit.version == 1
        payload = session.scalar(select(OutboxEvent)).payload
        assert payload["recipient_id"] == str(world.ids["owner"])
        assert "DEMO-123" not in json.dumps(payload)


@pytest.mark.parametrize(
    "actor,post,status,code",
    [
        ("owner", "found", 403, "SELF_CLAIM_FORBIDDEN"),
        ("claimant", "own", 403, "SELF_CLAIM_FORBIDDEN"),
        ("claimant", "closed", 409, "POST_NOT_CLAIMABLE"),
        ("claimant", "hidden", 404, "POST_NOT_FOUND"),
        ("claimant", "deleted", 404, "POST_NOT_FOUND"),
        ("claimant", "lost", 422, "POST_TYPE_NOT_FOUND"),
        ("locked", "found", 403, "ACCOUNT_FORBIDDEN"),
    ],
)
def test_invalid_user_or_post(world, actor, post, status, code):
    assert_error(create(world, actor, post=post), status, code)


def test_missing_post(world):
    assert_error(create(world, found_post_id=str(uuid4())), 404, "POST_NOT_FOUND")


@pytest.mark.parametrize("status", ["PENDING", "APPROVED"])
def test_active_duplicate_and_priority(world, status):
    world.add_claim(status=status)
    assert_error(create(world), 409, "DUPLICATE_ACTIVE_CLAIM")


@pytest.mark.parametrize("status", ["APPROVED", "RETURNED"])
def test_winner_blocks_new_claim_without_leaking_winner(world, status):
    winner_id = world.add_claim(claimant="other", status=status)
    response = create(world)
    assert_error(response, 409, "POST_ALREADY_ASSIGNED")
    assert str(winner_id) not in response.text
    assert str(world.ids["other"]) not in response.text


def test_rejected_allows_new_claim_and_preserves_history(world):
    rejected = world.add_claim(status="REJECTED")
    response = create(world)
    assert response.status_code == 201
    assert response.json()["id"] != str(rejected)
    assert len(world.client.get("/api/v1/claims/me", headers=world.auth()).json()["items"]) == 2


@pytest.mark.parametrize(
    "extra",
    [
        "claimant_id",
        "user_id",
        "status",
        "role",
        "decided_by",
        "file_path",
        "returned_by",
    ],
)
def test_rejects_mass_assignment(world, extra):
    assert_error(create(world, **{extra: "Fictional secret injected"}), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("evidence", [None, "", " " * 15, "short", "x" * 5001, 123, ["secret"]])
def test_invalid_evidence_never_echoes_input(world, evidence):
    response = create(world, evidence_description=evidence)
    assert_error(response, 422, "VALIDATION_ERROR")
    assert "x" * 100 not in response.text


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"found_post_id": "bad", "evidence_description": "Fictional secret data"},
        {"evidence_description": "Fictional secret data"},
        [],
    ],
)
def test_invalid_body(world, body):
    assert_error(
        world.client.post(
            "/api/v1/claims",
            json=body,
            headers=world.auth(),
        ),
        422,
        "VALIDATION_ERROR",
    )


@pytest.mark.parametrize(
    "path", ["/api/v1/claims", "/api/v1/claims/me", "/api/v1/claims/" + str(uuid4())]
)
@pytest.mark.parametrize("token", [None, "garbage", "Basic xyz"])
def test_requires_auth_on_every_route(world, path, token):
    headers = {} if token is None else {"Authorization": token}
    response = (
        world.client.post(path, json=world.body(), headers=headers)
        if path == "/api/v1/claims"
        else world.client.get(path, headers=headers)
    )
    assert_error(response, 401, "UNAUTHENTICATED")


def test_expired_token(world, expired_token):
    assert_error(
        world.client.get(
            "/api/v1/claims/me",
            headers={
                "Authorization": f"Bearer {expired_token}",
            },
        ),
        401,
        "UNAUTHENTICATED",
    )


@pytest.mark.parametrize(
    "change",
    [
        {"sub": str(uuid4())},
        {"sub": "malformed"},
        {"sub": None},
        {"aud": "other"},
        {"iss": "other"},
        {"token_version": 999},
        {"token_version": True},
        {"jti": []},
        {"iat": 9999999999},
        {"exp": None},
    ],
)
def test_invalid_token_claims(world, change):
    payload = jwt.decode(world.tokens["claimant"], options={"verify_signature": False})
    payload.update(change)
    token = jwt.encode(payload, world.settings.jwt_secret_key, algorithm="HS256")
    assert_error(
        world.client.get(
            "/api/v1/claims/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        ),
        401,
        "UNAUTHENTICATED",
    )


@pytest.mark.parametrize("field", ["exp", "iat", "sub", "jti", "token_version"])
def test_missing_required_token_claim(world, field):
    payload = jwt.decode(world.tokens["claimant"], options={"verify_signature": False})
    del payload[field]
    token = jwt.encode(payload, world.settings.jwt_secret_key, algorithm="HS256")
    assert_error(
        world.client.get(
            "/api/v1/claims/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        ),
        401,
        "UNAUTHENTICATED",
    )


def test_wrong_signature_and_algorithm(world):
    payload = jwt.decode(world.tokens["claimant"], options={"verify_signature": False})
    for secret, algorithm in [
        ("wrong-key-" * 8, "HS256"),
        (world.settings.jwt_secret_key, "HS384"),
    ]:
        token = jwt.encode(payload, secret, algorithm=algorithm)
        assert_error(
            world.client.get(
                "/api/v1/claims/me",
                headers={
                    "Authorization": f"Bearer {token}",
                },
            ),
            401,
            "UNAUTHENTICATED",
        )


def test_revoked_token_and_user_version(world):
    payload = jwt.decode(world.tokens["claimant"], options={"verify_signature": False})
    with world.factory() as session:
        session.add(RevokedToken(jti=payload["jti"], expires_at=utcnow() + timedelta(hours=1)))
        session.commit()
    assert_error(
        world.client.get("/api/v1/claims/me", headers=world.auth()), 401, "UNAUTHENTICATED"
    )
    with world.factory() as session:
        user = session.get(User, world.ids["owner"])
        user.token_version += 1
        session.commit()
    assert_error(
        world.client.get("/api/v1/claims/me", headers=world.auth("owner")), 401, "UNAUTHENTICATED"
    )


def test_list_relations_and_pagination_filter_in_database(world):
    now = utcnow()
    sent = world.add_claim(at=now - timedelta(seconds=3))
    received = world.add_claim(claimant="other", post="own", at=now - timedelta(seconds=2))
    unrelated = world.add_claim(claimant="other", post="unrelated", at=now)
    second_sent = world.add_claim(post="second", status="REJECTED", at=now - timedelta(seconds=1))
    expectations = {
        "claimant": {sent, second_sent},
        "reviewer": {received},
        "all": {sent, second_sent, received},
    }
    for relation, ids in expectations.items():
        response = world.client.get(f"/api/v1/claims/me?relation={relation}", headers=world.auth())
        assert_schema(response, "ClaimPage")
        assert {item["id"] for item in response.json()["items"]} == {str(id) for id in ids}
        assert str(unrelated) not in response.text and "evidence" not in response.text
    response = world.client.get("/api/v1/claims/me?relation=all&page_size=1", headers=world.auth())
    assert response.json()["items"][0]["id"] == str(second_sent)
    assert response.json()["has_next"] is True
    response = world.client.get(
        "/api/v1/claims/me?relation=all&page_size=1&page=3", headers=world.auth()
    )
    assert response.json()["items"][0]["id"] == str(sent)
    assert response.json()["has_next"] is False
    response = world.client.get("/api/v1/claims/me?page=999", headers=world.auth())
    assert response.json()["items"] == [] and response.json()["has_next"] is False
    response = world.client.get("/api/v1/claims/me?status=REJECTED", headers=world.auth())
    assert [item["id"] for item in response.json()["items"]] == [str(second_sent)]
    assert (
        world.client.get("/api/v1/claims/me?relation=all", headers=world.auth("admin")).json()[
            "items"
        ]
        == []
    )


def test_pagination_tiebreaker_is_id_desc(world):
    now = utcnow()
    ids = [world.add_claim(post=post, at=now) for post in ("found", "second")]
    response = world.client.get("/api/v1/claims/me", headers=world.auth())
    assert [item["id"] for item in response.json()["items"]] == [
        str(id) for id in sorted(ids, reverse=True)
    ]


def test_detail_evidence_only_for_exact_claim_parties(world):
    created = create(world)
    path = created.headers["Location"]
    competing_id = world.add_claim(claimant="other")
    with world.factory() as session:
        session.scalar(select(ClaimEvidence)).file_path = "private/never-expose.jpg"
        session.add(ClaimEvidence(claim_id=competing_id, private_content="COMPETITOR-SECRET"))
        session.commit()
    for actor in ("claimant", "owner"):
        response = world.client.get(path, headers=world.auth(actor))
        assert response.status_code == 200, response.text
        assert_schema(response, "ClaimDetail")
        assert (
            response.json()["evidence"][0]["private_content"] == "Fictional secret marking DEMO-123"
        )
        assert "file_path" not in response.text and "never-expose" not in response.text
        assert "COMPETITOR-SECRET" not in response.text
    for actor in ("other", "admin"):
        response = world.client.get(path, headers=world.auth(actor))
        assert_error(response, 404, "CLAIM_NOT_FOUND")
        missing = world.client.get(f"/api/v1/claims/{uuid4()}", headers=world.auth(actor))
        assert_error(missing, 404, "CLAIM_NOT_FOUND")
        assert response.json()["error"]["message"] == missing.json()["error"]["message"]
    # A claimant on the same post cannot read a competing claim's evidence.
    assert_error(
        world.client.get(f"/api/v1/claims/{competing_id}", headers=world.auth()),
        404,
        "CLAIM_NOT_FOUND",
    )


def test_unauthorized_detail_does_not_query_evidence(world):
    claim_id = world.add_claim()
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(world.engine, "before_cursor_execute", record)
    try:
        response = world.client.get(f"/api/v1/claims/{claim_id}", headers=world.auth("other"))
    finally:
        event.remove(world.engine, "before_cursor_execute", record)
    assert_error(response, 404, "CLAIM_NOT_FOUND")
    assert not any("claim_evidence" in statement for statement in statements)


@pytest.mark.parametrize(
    "query",
    [
        "user_id=anything",
        "role=ADMIN",
        "relation=everyone",
        "page=0",
        "page_size=101",
        "page_size=0",
        "status=CANCELLED",
        "page=1.5",
        "page_size=abc",
    ],
)
def test_list_validation(world, query):
    assert_error(
        world.client.get(f"/api/v1/claims/me?{query}", headers=world.auth()),
        422,
        "VALIDATION_ERROR",
    )


def test_detail_validation_and_extra_query(world):
    assert_error(
        world.client.get("/api/v1/claims/bad-uuid", headers=world.auth()), 422, "VALIDATION_ERROR"
    )
    assert_error(
        world.client.get(f"/api/v1/claims/{uuid4()}?user_id=other", headers=world.auth()),
        422,
        "VALIDATION_ERROR",
    )
    assert_error(
        world.client.post("/api/v1/claims?user_id=other", json=world.body(), headers=world.auth()),
        422,
        "VALIDATION_ERROR",
    )


@pytest.mark.parametrize("path", ["/api/v1/claims/me", "/api/v1/claims/" + str(uuid4())])
def test_get_rejects_body(world, path):
    assert_error(
        world.client.request(
            "GET", path, json={"secret": "Fictional secret"}, headers=world.auth()
        ),
        422,
        "VALIDATION_ERROR",
    )


@pytest.mark.parametrize("table", ["claim_evidence", "audit_logs", "outbox_events"])
def test_atomic_rollback_and_sanitized_server_errors(world, table, caplog):
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT") and table in statement:
            raise SQLAlchemyError("Fictional secret from storage must never reach logs")

    event.listen(world.engine, "before_cursor_execute", fail)
    try:
        response = create(world)
    finally:
        event.remove(world.engine, "before_cursor_execute", fail)
    assert response.status_code == 500
    assert response.headers["Cache-Control"] == "no-store"
    assert "Fictional secret" not in response.text and "Fictional secret" not in caplog.text
    with world.factory() as session:
        for model in (Claim, ClaimEvidence, AuditLog, OutboxEvent):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_return_summary_is_serialized_without_private_fields(world):
    claim_id = world.add_claim(status="APPROVED")
    with world.factory() as session:
        session.add(ReturnRecord(claim_id=claim_id, status="HANDED_OVER", handed_over_at=utcnow()))
        session.commit()
    response = world.client.get(f"/api/v1/claims/{claim_id}", headers=world.auth())
    assert_schema(response, "ClaimDetail")
    assert response.json()["return_summary"]["status"] == "HANDED_OVER"


def test_swagger_and_runtime_openapi_preserve_claim_operations(world):
    response = world.client.get("/docs")
    assert response.status_code == 200
    assert "/swagger-assets/swagger-ui-bundle.js" in response.text
    assert world.client.get("/swagger-assets/swagger-ui-bundle.js").status_code == 200
    spec = world.client.get("/openapi.json").json()
    assert set(CONTRACT["paths"]) <= set(spec["paths"])
    for path, operations in CONTRACT["paths"].items():
        for method in operations:
            assert spec["paths"][path][method]["security"] == [{"BearerAuth": []}]
    assert "BearerAuth" in spec["components"]["securitySchemes"]
