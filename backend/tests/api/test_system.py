import base64
from io import BytesIO
from uuid import UUID

from openapi_spec_validator import validate
from PIL import Image
from sqlalchemy import func, select

from app.modules.notifications_admin.models.report import ModerationAudit

API = "/api/v1"


def test_integrated_openapi_lists_all_business_operations(world):
    spec = payload(world.client.get("/openapi.json"))
    validate(spec)
    assert sum(len(operations) for operations in spec["paths"].values()) == 39
    assert f"{API}/auth/refresh" in spec["paths"]
    assert f"{API}/returns/{{id}}/handover" in spec["paths"]
    assert f"{API}/admin/statistics" in spec["paths"]
    assert payload(world.client.get(f"{API}/health"))["database"] == "healthy"


def payload(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def image_bytes() -> bytes:
    target = BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(target, format="PNG")
    return target.getvalue()


def create_post(world, actor="owner", post_type="FOUND", **changes):
    category = payload(world.client.get(f"{API}/categories"))[0]["id"]
    body = {
        "type": post_type,
        "title": "Ví xanh có hình ngôi sao",
        "description": "Ví xanh nhãn hiệu FindBack",
        "category_id": category,
        "location": "Khu vực công cộng",
        "location_code": "VN-HN",
        "event_time": "2026-11-17T10:00:00+07:00",
        "color_code": "BLUE",
        "material": "Da",
        **changes,
    }
    return payload(world.client.post(f"{API}/posts", json=body, headers=world.auth(actor)), 201)


def test_register_login_refresh_and_safe_profiles(world):
    client = world.client
    auth = f"{API}/auth"
    body = {"email": "Owner123@example.com", "password": "Example!2026", "full_name": "Test Owner"}
    registered = payload(client.post(f"{auth}/register", json=body), 201)
    UUID(registered["id"])
    assert "password_hash" not in registered
    assert client.post(f"{auth}/register", json=body).status_code == 409
    assert client.post(f"{auth}/login", json={**body, "password": "wrong"}).status_code == 422
    login = {"email": body["email"].lower(), "password": body["password"]}
    assert client.post(f"{auth}/login", json={**login, "password": "wrong"}).status_code == 401
    first = payload(client.post(f"{auth}/login", json=login))
    renewed = payload(
        client.post(f"{auth}/refresh", json={"refresh_token": first["refresh_token"]})
    )
    assert renewed["refresh_token"] != first["refresh_token"]
    assert (
        client.post(f"{auth}/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.post(
            f"{auth}/refresh", json={"refresh_token": first["access_token"][:128]}
        ).status_code
        == 401
    )
    headers = {"Authorization": f"Bearer {renewed['access_token']}"}
    me = f"{API}/users/me"
    assert payload(client.get(me, headers=headers))["id"] == registered["id"]
    assert client.patch(me, json={"role": "ADMIN"}, headers=headers).status_code == 422
    result = payload(
        client.patch(me, json={"full_name": "Public name", "phone": "0900000000"}, headers=headers)
    )
    public = payload(client.get(f"{API}/users/{registered['id']}"))
    assert result["phone"] == "0900000000"
    assert public == {"id": registered["id"], "full_name": "Public name", "avatar_url": None}


def test_posts_search_matching_and_images_use_the_same_visibility(world):
    client = world.client
    lost = create_post(world, "claimant", "LOST", event_time="2026-11-17T05:00:00Z")
    found = create_post(world)
    found_url = f"{API}/posts/{found['id']}"
    assert payload(client.get(found_url))["id"] == found["id"]
    assert any(item["id"] == found["id"] for item in payload(client.get(f"{API}/posts"))["items"])
    my_posts = payload(client.get(f"{API}/users/me/posts", headers=world.auth("claimant")))["items"]
    assert lost["id"] in {item["id"] for item in my_posts}
    assert found["id"] not in {item["id"] for item in my_posts}
    assert (
        client.patch(found_url, json={"title": "Unauthorized"}, headers=world.auth()).status_code
        == 403
    )

    query = {
        "q": "ví xanh",
        "type": "FOUND",
        "location_code": "VN-HN",
        "category_id": found["category_id"],
        "material": " DA ",
        "event_from": "2026-11-17T03:00:00Z",
        "event_to": "2026-11-17T11:00:00+07:00",
        "page_size": 1,
    }
    search = payload(client.get(f"{API}/search", params=query))
    assert [item["id"] for item in search["items"]] == [found["id"]]
    assert search["pagination"]["total"] == 1
    beyond = payload(client.get(f"{API}/search", params={**query, "page": 2}))
    assert beyond["items"] == [] and beyond["pagination"]["total"] == 1
    assert client.get(f"{API}/search?page=1&page=2").status_code == 422
    assert client.get(f"{API}/search?location_code=UNKNOWN").status_code == 422

    image = payload(
        client.post(
            f"{found_url}/images",
            files={"file": ("post.png", image_bytes(), "image/png")},
            headers=world.auth("owner"),
        ),
        201,
    )["image"]
    assert client.get(image["file_path"]).headers["content-type"] == "image/png"
    assert (
        client.post(
            f"{found_url}/images",
            files={"file": ("post.png", b"invalid", "image/png")},
            headers=world.auth("owner"),
        ).status_code
        == 415
    )

    params = {"post_id": lost["id"]}
    assert client.get(f"{API}/matches", params=params).status_code == 409
    assert (
        client.post(
            f"{API}/matches/recalculate", json=params, headers=world.auth("other")
        ).status_code
        == 403
    )
    calculated = payload(
        client.post(f"{API}/matches/recalculate", json=params, headers=world.auth())
    )
    assert len(calculated["items"]) == 1
    match = payload(client.get(f"{API}/matches", params=params))["items"][0]
    assert match["candidate"]["id"] == found["id"]
    assert payload(client.get(f"{API}/matches/{match['id']}"))["score"] >= 75

    payload(
        client.patch(found_url, json={"title": "Ví xanh cập nhật"}, headers=world.auth("owner"))
    )
    assert client.get(f"{API}/matches", params=params).status_code == 409
    payload(client.post(f"{API}/matches/recalculate", json=params, headers=world.auth()))
    payload(
        client.patch(
            f"{API}/admin/posts/{found['id']}/moderation",
            json={"action": "HIDE", "reason": "Policy violation"},
            headers=world.auth("admin"),
        )
    )
    assert client.get(found_url).status_code == 404
    assert client.get(image["file_path"]).status_code == 404
    assert payload(client.get(f"{API}/search", params=query))["items"] == []
    assert payload(client.get(f"{API}/matches", params=params))["items"] == []
    assert client.get(f"{API}/matches/{match['id']}").status_code == 404
    assert client.delete(f"{API}/posts/{lost['id']}", headers=world.auth()).status_code == 204


def test_claim_handover_private_evidence_and_notifications(world):
    client = world.client
    owner = world.auth("owner")
    claimant = world.auth()
    post = create_post(world)
    claim = payload(
        client.post(
            f"{API}/claims",
            headers=claimant,
            json={
                "found_post_id": post["id"],
                "evidence_description": "Mô tả riêng của người nhận đồ",
            },
        ),
        201,
    )
    url = f"{API}/claims/{claim['id']}"
    body = {
        "expected_version": 1,
        "evidence_description": "Ký hiệu riêng tư ở mặt trong",
        "image_base64": base64.b64encode(image_bytes()).decode(),
        "image_content_type": "image/png",
    }
    assert client.post(f"{url}/evidence", json=body, headers=owner).status_code == 403
    enriched = payload(client.post(f"{url}/evidence", json=body, headers=claimant), 201)
    evidence = next(
        item
        for item in enriched["evidence"]
        if item["private_content"] == body["evidence_description"]
    )
    download = f"{url}/evidence/{evidence['id']}/file"
    assert client.get(download, headers=world.auth("admin")).status_code == 404
    assert client.get(download, headers=owner).headers["content-type"] == "image/png"
    assert client.post(f"{url}/evidence", json=body, headers=claimant).status_code == 409

    approved = payload(client.patch(f"{url}/approve", json={"expected_version": 2}, headers=owner))
    assert approved["status"] == "APPROVED"
    arrange = {"claim_id": claim["id"], "expected_version": 3, "meeting_note": "Điểm hẹn riêng"}
    assert client.post(f"{API}/returns", json=arrange, headers=claimant).status_code == 403
    handover = payload(client.post(f"{API}/returns", json=arrange, headers=owner), 201)
    return_url = f"{API}/returns/{handover['id']}"
    assert client.get(return_url, headers=world.auth("other")).status_code == 404
    assert payload(client.get(return_url, headers=claimant))["status"] == "ARRANGED"
    complete = {"expected_version": 4, "receipt_confirmed": True}
    assert client.patch(f"{url}/complete", json=complete, headers=claimant).status_code == 409
    assert (
        client.patch(
            f"{return_url}/handover", json={"expected_version": 4}, headers=claimant
        ).status_code
        == 403
    )
    handed_over = payload(
        client.patch(f"{return_url}/handover", json={"expected_version": 4}, headers=owner)
    )
    assert handed_over["status"] == "HANDED_OVER"
    complete["expected_version"] = 5
    returned = payload(client.patch(f"{url}/complete", json=complete, headers=claimant))
    assert returned["status"] == "RETURNED" and returned["return_summary"]["status"] == "CONFIRMED"
    assert payload(client.get(f"{API}/posts/{post['id']}"))["status"] == "CLOSED"

    notifications = payload(client.get(f"{API}/notifications", headers=owner))["items"]
    assert {item["type"] for item in notifications} == {
        "CLAIM_CREATED",
        "CLAIM_EVIDENCE_ADDED",
        "CLAIM_COMPLETED",
    }
    assert body["evidence_description"] not in str(notifications)
    mark = f"{API}/notifications/{notifications[0]['id']}/read"
    assert client.patch(mark, headers=claimant).status_code == 404
    assert payload(client.patch(mark, headers=owner)) == payload(client.patch(mark, headers=owner))
    assert (
        payload(client.get(f"{API}/notifications", params={"is_read": False}, headers=owner))[
            "pagination"
        ]["total"]
        == 2
    )


def test_reporting_admin_statistics_and_audit(world):
    client = world.client
    user = world.auth("claimant")
    admin = world.auth("admin")
    post = create_post(world)
    body = {"post_id": post["id"], "reason": "Thông tin bài không hợp lệ"}
    assert client.post(f"{API}/reports", json=body).status_code == 401
    report = payload(client.post(f"{API}/reports", json=body, headers=user), 201)
    assert client.post(f"{API}/reports", json=body, headers=user).status_code == 409
    assert client.get(f"{API}/admin/reports", headers=user).status_code == 403
    assert client.get(f"{API}/admin/statistics", headers=user).status_code == 403
    assert (
        payload(client.get(f"{API}/admin/reports", headers=admin))["items"][0]["id"] == report["id"]
    )
    stats = payload(client.get(f"{API}/admin/statistics", headers=admin))
    assert stats["pending_reports"] == 1 and stats["resolved_reports"] == 0
    target = f"{API}/admin/reports/{report['id']}"
    resolved = payload(
        client.patch(
            target,
            headers=admin,
            json={
                "status": "RESOLVED",
                "resolution_note": "Đã xem xét nội dung",
            },
        )
    )
    assert resolved["reviewed_by"] == str(world.ids["admin"])
    assert (
        client.patch(
            target,
            headers=admin,
            json={
                "status": "DISMISSED",
                "resolution_note": "Đã đóng",
            },
        ).status_code
        == 409
    )
    stats = payload(client.get(f"{API}/admin/statistics", headers=admin))
    assert stats["pending_reports"] == 0 and stats["resolved_reports"] == 1
    assert payload(client.get(f"{API}/admin/posts", headers=admin))["items"]
    with world.factory() as db:
        assert db.scalar(select(func.count()).select_from(ModerationAudit)) == 1
