from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.modules.matching.repositories.snapshots import MemoryMatchingStore
from app.modules.matching.schemas.contracts import MatchesResponse


def setup(make_post, candidates=None):
    source = make_post()
    store = MemoryMatchingStore([source, *(candidates if candidates is not None else [make_post(2, "FOUND")])])
    store.recalculate(source.post.id)
    client = TestClient(create_app(store))
    return store, client, {"post_id": str(source.post.id)}


def test_matches_schema_and_public_projection(make_post):
    _, client, query = setup(make_post)
    response = client.get("/api/v1/matches", params=query)
    assert response.status_code == 200
    result = MatchesResponse.model_validate(response.json())
    item = result.items[0]
    assert item.score == 100
    assert item.level == "HIGH"
    assert result.pagination.total == 1
    assert item.candidate.event_time.utcoffset() == timedelta(0)
    assert set(response.json()["items"][0]) == {"id", "lost_post_id", "found_post_id", "candidate", "score", "level", "score_details", "explanation"}
    assert "cần xác minh" in item.explanation
    for private in ("claim_evidence", "owner_confirmed", "email", "password", "serial", "token"):
        assert private not in response.text


def test_rank_before_pagination_min_score_and_reverse(make_post):
    store, client, query = setup(make_post, [make_post(4, "FOUND"), make_post(2, "FOUND"), make_post(3, "FOUND", color_code=None)])
    result = client.get("/api/v1/matches", params={**query, "page_size": 1, "page": 2}).json()
    assert UUID(result["items"][0]["candidate"]["id"]).int == 4
    assert result["pagination"]["total"] == 3
    assert result["pagination"]["has_previous"] is True
    assert result["pagination"]["has_next"] is True
    assert client.get("/api/v1/matches", params={**query, "min_score": "90.01"}).json()["pagination"]["total"] == 2
    assert client.get("/api/v1/matches", params={**query, "page": 100}).json()["items"] == []
    store.recalculate(UUID(int=2))
    reverse = client.get("/api/v1/matches", params={"post_id": str(UUID(int=2))}).json()["items"][0]
    assert UUID(reverse["candidate"]["id"]).int == 1
    assert UUID(reverse["lost_post_id"]).int == 1


def test_levels_75_and_50(make_post):
    source = make_post()
    _, client, query = setup(make_post, [
        make_post(2, "FOUND", location={"code": "AREA_B", "name": "Khu B"}),
        make_post(3, "FOUND", title="tai nghe", description="tai nghe", color_code=None, public_attributes={}, event_time=source.post.event_time + timedelta(days=10)),
    ])
    items = client.get("/api/v1/matches", params=query).json()["items"]
    assert [(item["score"], item["level"]) for item in items] == [(75, "HIGH"), (50, "POSSIBLE")]


def test_visibility_freshness_and_new_candidate(make_post):
    store, client, query = setup(make_post)
    store.put(make_post(2, "FOUND", is_public=False))
    hidden = client.get("/api/v1/matches", params=query)
    assert hidden.status_code == 200
    assert hidden.json()["pagination"]["total"] == 0
    store.put(make_post(3, "FOUND"))
    assert client.get("/api/v1/matches", params=query).json()["error"]["code"] == "MATCHES_NOT_READY"
    store.recalculate(UUID(int=1))
    store.put(make_post(3, "FOUND", title="ví gấp mới"))
    assert client.get("/api/v1/matches", params=query).status_code == 409
    store.recalculate(UUID(int=1))
    store.put(make_post(title="ví gấp mới"))
    assert client.get("/api/v1/matches", params=query).status_code == 409


def test_not_found_not_eligible_and_zero_results(make_post):
    store, client, query = setup(make_post, [])
    assert client.get("/api/v1/matches", params=query).json()["items"] == []
    store.put(make_post(is_public=False))
    hidden = client.get("/api/v1/matches", params=query)
    missing = client.get("/api/v1/matches", params={"post_id": str(UUID(int=999))})
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    store.put(make_post(status="CLOSED"))
    assert client.get("/api/v1/matches", params=query).json()["error"]["code"] == "POST_NOT_MATCHABLE"


def test_never_calculated_and_default_unconfigured_adapter(make_post):
    store = MemoryMatchingStore([make_post()])
    client = TestClient(create_app(store))
    assert client.get("/api/v1/matches", params={"post_id": str(UUID(int=1))}).json()["error"]["code"] == "MATCHES_NOT_READY"
    assert TestClient(create_app()).get("/api/v1/matches", params={"post_id": str(UUID(int=1))}).status_code == 503


@pytest.mark.parametrize("extra", [{"page": "1.0"}, {"page_size": "true"}, {"page": 0}, {"page_size": 101}, {"min_score": "NaN"}, {"min_score": "Infinity"}, {"min_score": "49.99"}, {"min_score": "100.01"}, {"min_score": "50.001"}, {"sort": "newest"}, {"q": "ví"}, {"post_id": "invalid"}, {"page_size": ""}])
def test_invalid_queries(make_post, extra):
    _, client, query = setup(make_post)
    response = client.get("/api/v1/matches", params={**query, **extra})
    assert response.status_code == 422
    assert set(response.json()) == {"error"}
    assert response.json()["error"]["details"]


def test_missing_duplicate_and_private_query_not_echoed(make_post):
    _, client, query = setup(make_post)
    assert client.get("/api/v1/matches").status_code == 422
    assert client.get("/api/v1/matches", params=[*query.items(), ("page", "1"), ("page", "1")]).json()["error"]["code"] == "DUPLICATE_QUERY_PARAMETER"
    response = client.get("/api/v1/matches", params={**query, "evidence": "PRIVATE_SENTINEL"})
    assert response.json()["error"]["code"] == "UNKNOWN_QUERY_PARAMETER"
    assert "PRIVATE_SENTINEL" not in response.text


def test_openapi_exposes_query_and_response(make_post):
    _, client, _ = setup(make_post)
    operation = client.get("/openapi.json").json()["paths"]["/api/v1/matches"]["get"]
    assert {item["name"] for item in operation["parameters"]} == {"post_id", "min_score", "page", "page_size", "sort"}
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("MatchesResponse")


def test_unexpected_error_does_not_leak_private_data():
    class BrokenReader:
        def read(self, source_id):
            raise RuntimeError("PRIVATE_SENTINEL")
    client = TestClient(create_app(BrokenReader()), raise_server_exceptions=False)
    response = client.get("/api/v1/matches", params={"post_id": str(UUID(int=1))})
    assert response.status_code == 500
    assert "PRIVATE_SENTINEL" not in response.text


def test_demo_factory_serves_documented_request():
    from app.demo import SOURCE_ID, create_demo_app

    client = TestClient(create_demo_app())
    response = client.get("/api/v1/matches", params={"post_id": SOURCE_ID})
    assert response.status_code == 200
    assert response.json()["items"][0]["score"] == 100
