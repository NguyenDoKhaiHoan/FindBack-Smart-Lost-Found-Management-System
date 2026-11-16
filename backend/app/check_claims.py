"""Check a running local API with fictional demo accounts; save sanitized results."""

import json
from uuid import UUID, uuid4

import httpx

from app.core.config import BACKEND_DIR, Settings
from app.db import models  # noqa: F401
from app.db.session import make_engine, make_session_factory
from app.modules.posts.models.post import Post


def main():
    settings = Settings()
    if settings.app_env != "development":
        raise SystemExit("Live demo checks require APP_ENV=development")
    demo = json.loads((BACKEND_DIR / ".local/claims-demo.json").read_text(encoding="utf-8"))
    post_id = uuid4()
    engine = make_engine(settings)
    with make_session_factory(engine)() as session:
        session.add(
            Post(
                id=post_id,
                owner_id=UUID(demo["users"]["owner"]["id"]),
                type="FOUND",
                status="OPEN",
                is_hidden=False,
            )
        )
        session.commit()
    engine.dispose()
    results = []

    def auth(name):
        return {"Authorization": "Bearer " + demo["users"][name]["token"]}

    def check(name, response, expected_status, expected_code=None):
        passed = response.status_code == expected_status
        passed = passed and response.headers.get("Cache-Control") == "no-store"
        if expected_code:
            passed = passed and response.json().get("error", {}).get("code") == expected_code
        results.append(
            {
                "check": name,
                "status": response.status_code,
                "expected_status": expected_status,
                "passed": passed,
            }
        )
        if not passed:
            raise AssertionError(f"Check failed: {name} (HTTP {response.status_code})")

    body = {"found_post_id": str(post_id), "evidence_description": "Fictional DEMO-SMOKE evidence"}
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
        response = client.post("/api/v1/claims", json=body, headers=auth("claimant"))
        check("create PENDING from JWT", response, 201)
        assert response.json()["status"] == "PENDING"
        assert response.json()["claimant_id"] == demo["users"]["claimant"]["id"]
        assert "DEMO-SMOKE" not in response.text
        path = response.headers["Location"]
        for actor in ("claimant", "owner"):
            response = client.get(path, headers=auth(actor))
            check(f"detail allowed: {actor}", response, 200)
            assert response.json()["evidence"][0]["private_content"] == body["evidence_description"]
        for actor in ("outsider", "admin"):
            response = client.get(path, headers=auth(actor))
            check(f"detail hidden: {actor}", response, 404, "CLAIM_NOT_FOUND")
            assert "DEMO-SMOKE" not in response.text
        check("anonymous detail", client.get(path), 401, "UNAUTHENTICATED")
        check(
            "duplicate open claim",
            client.post("/api/v1/claims", json=body, headers=auth("claimant")),
            409,
            "DUPLICATE_ACTIVE_CLAIM",
        )
        check(
            "self claim",
            client.post("/api/v1/claims", json=body, headers=auth("owner")),
            403,
            "SELF_CLAIM_FORBIDDEN",
        )
        response = client.get("/api/v1/claims/me", headers=auth("claimant"))
        check("my claims exclude evidence", response, 200)
        assert "DEMO-SMOKE" not in response.text and "evidence" not in response.text
        response = client.get("/api/v1/claims/me?relation=reviewer", headers=auth("owner"))
        check("owner reviewer list excludes evidence", response, 200)
        assert "DEMO-SMOKE" not in response.text
        response = client.get("/api/v1/claims/me?relation=all", headers=auth("admin"))
        check("admin cannot list unrelated claims", response, 200)
        assert response.json()["items"] == []
        check(
            "reject forged actor",
            client.post(
                "/api/v1/claims",
                headers=auth("claimant"),
                json={**body, "claimant_id": str(uuid4())},
            ),
            422,
            "VALIDATION_ERROR",
        )
        check(
            "reject LOST post",
            client.post(
                "/api/v1/claims",
                headers=auth("claimant"),
                json={**body, "found_post_id": demo["posts"]["lost"]},
            ),
            422,
            "POST_TYPE_NOT_FOUND",
        )
        check(
            "reject missing post",
            client.post(
                "/api/v1/claims",
                headers=auth("claimant"),
                json={**body, "found_post_id": str(uuid4())},
            ),
            404,
            "POST_NOT_FOUND",
        )
    report = BACKEND_DIR / ".local/claims-live-checks.json"
    report.write_text(
        json.dumps({"target": "local PostgreSQL API", "checks": results}, indent=2),
        encoding="utf-8",
    )
    print(f"{len(results)} live checks passed. Sanitized report: {report}")


if __name__ == "__main__":
    main()
