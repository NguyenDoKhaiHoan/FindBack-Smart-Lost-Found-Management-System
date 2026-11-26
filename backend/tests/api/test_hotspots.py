import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.hotspots import service
from app.modules.identity.models.user import User
from app.modules.posts.models.post import Category, Post
from app.modules.posts.services.listings import update_search_text

PUBLIC = "/api/ai/hotspots"
ADMIN = "/api/admin/ai/hotspots"
NOW = datetime(2026, 11, 24, 7, tzinfo=timezone.utc)


@pytest.fixture
def history(world, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: NOW)
    with world.factory() as db:
        document, electronics = (
            db.scalar(select(Category.id).where(Category.name == name))
            for name in ("Giấy tờ", "Thiết bị điện tử")
        )
        people = [User(id=uuid4(), role="USER") for _ in range(6)]
        db.add_all(people)
        db.flush()

        def add(owner, **changes):
            values = {
                "owner_id": owner,
                "type": "LOST",
                "status": "OPEN",
                "category_id": document,
                "title": "Thẻ sinh viên",
                "description": "Thẻ có logo",
                "location_code": "VN-HN",
                "location": "Địa chỉ riêng không dùng làm nhãn cụm",
                "hotspot_zone": "LIBRARY",
                "latitude": 21.024,
                "longitude": 105.812,
                "event_time": NOW - timedelta(days=2),
                "created_at": NOW,
            }
            post = Post(id=uuid4(), **(values | changes))
            update_search_text(post)
            db.add(post)
            return post.id

        ids = [
            add(
                person.id,
                status="CLOSED" if index == 0 else "OPEN",
                title="Thẻ sinh viên · 0901234567" if index == 2 else "Thẻ sinh viên",
            )
            for index, person in enumerate(people)
        ]
        # The older submitted report represents the two rows with identical event data.
        add(people[1].id, created_at=NOW + timedelta(seconds=1))
        for person in people[:5]:
            add(person.id, event_time=NOW - timedelta(days=33))
        for index in range(5):
            add(
                people[0].id,
                latitude=10.772,
                longitude=106.691,
                location_code="VN-SG",
                hotspot_zone="PARKING",
                category_id=electronics,
                title=f"Điện thoại {index}",
            )
        add(
            people[0].id,
            latitude=16.062,
            longitude=108.21,
            category_id=electronics,
            location_code="VN-DN",
        )
        add(people[0].id, type="FOUND")
        add(people[0].id, is_hidden=True)
        add(people[0].id, deleted_at=NOW)
        add(people[0].id, latitude=99)
        add(people[0].id, hotspot_zone=None)
        add(people[0].id, event_time=NOW + timedelta(minutes=5))
        db.commit()
        return ids, document, electronics


def test_public_hotspots_are_coarse_and_suppress_small_reporter_groups(world, history):
    ids, document, electronics = history
    result = world.client.get(PUBLIC)
    assert result.status_code == 200, result.text
    body = result.json()
    stats = body["statistics"]
    assert stats["total_events"] == 6
    assert stats["total_hotspots"] == 1
    assert stats["noise_events"] is None and stats["trend"] is None
    assert stats["timeline"] == []
    [cluster] = body["clusters"]
    assert cluster["latitude"] == 21.02 and cluster["longitude"] == 105.81
    assert cluster["location_name"] == "Thư viện · Hà Nội"
    assert cluster["peak_time"] == {"label": "14:00–16:00", "count": 6}
    assert cluster["top_categories"] == [{"label": "Giấy tờ", "count": 6}]
    assert cluster["timeline"] == [] and cluster["trend"] is None
    assert "Địa chỉ riêng" not in result.text

    details = world.client.get(f"{PUBLIC}/{cluster['cluster_id']}")
    assert details.status_code == 200
    rows = details.json()["related_posts"]
    assert set(row["id"] for row in rows) <= set(map(str, ids))
    assert len(rows) == 6
    assert set(rows[0]) == {"id", "title", "event_day"}
    assert "0901234567" not in details.text
    heat = world.client.get(f"{PUBLIC}/heatmap").json()["heatmap"]
    assert heat == body["heatmap"] and len(heat) == 1

    assert (
        world.client.get(PUBLIC, params={"category_id": str(electronics)}).json()["clusters"] == []
    )
    assert world.client.get(PUBLIC, params={"location_id": "VN-SG"}).json()["clusters"] == []
    assert world.client.get(
        PUBLIC, params={"zone": "LIBRARY", "category_id": str(document)}
    ).json()["clusters"] == [cluster]
    assert (
        world.client.get(f"{PUBLIC}/{cluster['cluster_id']}", params={"period": "90"}).status_code
        == 404
    )
    assert world.client.get(PUBLIC, params={"start_date": "2026-11-24"}).status_code == 422
    assert world.client.get(PUBLIC, params={"period": "8"}).status_code == 422
    assert world.client.get(PUBLIC, params={"location_id": "UNKNOWN"}).status_code == 422
    assert world.client.get(PUBLIC, params={"role": "ADMIN"}).status_code == 422


def test_admin_filters_trends_and_persistent_configuration(world, history):
    _, _, electronics = history
    admin = world.auth("admin")
    assert world.client.get(ADMIN).status_code == 401
    for method, path in (
        ("GET", ADMIN),
        ("GET", f"{ADMIN}/config"),
        ("PATCH", f"{ADMIN}/config"),
        ("POST", f"{ADMIN}/recalculate"),
        ("GET", f"{ADMIN}/export"),
    ):
        assert (
            world.client.request(
                method, path, headers=world.auth(), json={} if method == "PATCH" else None
            ).status_code
            == 403
        )

    report = world.client.get(ADMIN, headers=admin)
    assert report.status_code == 200, report.text
    data = report.json()
    stats = data["statistics"]
    assert stats["total_events"] == 12
    assert stats["total_hotspots"] == 2
    assert stats["noise_events"] == 1
    assert stats["trend"] == {"previous_count": 5, "change_percent": 140}
    assert sum(row["count"] for row in stats["timeline"]) == 12
    first, second = data["clusters"]
    assert first["trend"] == {"previous_count": 5, "change_percent": 20}
    assert second["trend"] is None
    assert world.client.get(f"{PUBLIC}/{second['cluster_id']}").status_code == 404
    assert world.client.get(f"{ADMIN}/{second['cluster_id']}", headers=admin).status_code == 200
    limited = world.client.get(
        ADMIN,
        headers=admin,
        params={
            "start_date": "2026-11-21",
            "end_date": "2026-11-22",
            "category_id": str(electronics),
            "location_id": "VN-SG",
            "group_by": "week",
        },
    ).json()["statistics"]
    assert limited["total_events"] == 5
    assert len(limited["timeline"]) == 1

    assert (
        world.client.patch(f"{ADMIN}/config", headers=admin, json={"eps_meters": 5}).status_code
        == 422
    )
    assert (
        world.client.patch(f"{ADMIN}/config", headers=admin, json={"high_count": 100}).status_code
        == 422
    )
    changed = world.client.patch(f"{ADMIN}/config", headers=admin, json={"min_samples": 7})
    assert changed.status_code == 200
    assert world.client.get(f"{ADMIN}/config", headers=admin).json()["min_samples"] == 7
    assert world.client.get(PUBLIC).json()["clusters"] == []
    recomputed = world.client.post(f"{ADMIN}/recalculate", headers=admin)
    assert recomputed.status_code == 200 and recomputed.json()["clusters"] == []
    csv = world.client.get(f"{ADMIN}/export", headers=admin)
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert "cluster_id,area,reports" in csv.text


def test_post_pin_requires_consent_and_owner_access(world, history):
    _, category, _ = history
    base = {
        "type": "LOST",
        "title": "Vợt",
        "location": "Khu thể thao",
        "category_id": str(category),
        "event_time": NOW.isoformat(),
        "description": "Vợt sợi đen",
        "location_code": "VN-HN",
    }
    coords = {"latitude": 21.023415, "longitude": 105.814552}
    pin = {"hotspot_zone": "SPORTS", **coords}
    auth = world.auth()
    posted = world.client.post("/api/v1/posts", headers=auth, json={**base, **pin})
    assert posted.status_code == 201, posted.text
    detail = f"/api/v1/posts/{posted.json()['id']}"
    assert "latitude" not in world.client.get(detail).json()
    assert (
        world.client.get(f"{detail}/hotspot-location", headers=world.auth("other")).status_code
        == 404
    )
    assert world.client.get(f"{detail}/hotspot-location", headers=auth).json() == {
        "latitude": 21.023,
        "longitude": 105.815,
        "hotspot_zone": "SPORTS",
    }
    assert (
        world.client.get(ADMIN, headers=world.auth("admin")).json()["statistics"]["total_events"]
        == 13
    )
    cleared = world.client.patch(detail, headers=auth, json=dict.fromkeys(pin))
    assert cleared.status_code == 200
    assert world.client.get(f"{detail}/hotspot-location", headers=auth).json() is None
    assert (
        world.client.get(ADMIN, headers=world.auth("admin")).json()["statistics"]["total_events"]
        == 12
    )
    assert (
        world.client.post(
            "/api/v1/posts", headers=auth, json={**base, **pin, "type": "FOUND"}
        ).status_code
        == 422
    )
    assert (
        world.client.post(
            "/api/v1/posts", headers=auth, json={**base, "hotspot_zone": "SPORTS"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("get_lost_item_hotspots", "Thư viện · Hà Nội"),
        ("get_hotspot_statistics", "6 báo cáo"),
        ("get_top_lost_categories", "Giấy tờ"),
        ("get_peak_lost_hours", "14:00–16:00"),
    ],
)
def test_chat_tools_use_the_same_service_and_authenticated_scope(
    world, history, monkeypatch, name, expected
):
    arguments = {
        "period": "30",
        "location_id": None,
        "zone": None,
        "unsupported_place": False,
        "managed_only": False,
    }

    def reply(feature, **request):
        assert feature == "chat"
        schemas = {tool["name"]: tool["parameters"] for tool in request["tools"]}
        assert name in schemas
        assert "role" not in schemas[name]["properties"]
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    name=name,
                    arguments=json.dumps(arguments),
                )
            ]
        )

    monkeypatch.setattr(world.client.app.state.ai, "responses", reply)
    message = {"message": "Cho tôi xem thống kê mất đồ trong 30 ngày"}
    public_reply = world.client.post("/api/ai/chat", headers=world.auth(), json=message)
    assert public_reply.status_code == 200, public_reply.text
    assert expected in public_reply.json()["reply"]
    assert public_reply.json()["action"] == "hotspots"
    if name == "get_hotspot_statistics":
        admin_reply = world.client.post("/api/ai/chat", headers=world.auth("admin"), json=message)
        assert "12 báo cáo" in admin_reply.json()["reply"]
        assert admin_reply.json()["action"] == "hotspots_admin"
        arguments["managed_only"] = True
        denied = world.client.post("/api/ai/chat", headers=world.auth(), json=message)
        assert "chưa có phân quyền" in denied.json()["reply"]
