"""Seed repeatable fictional reports in a dedicated local SQLite database."""

import argparse
import os
import random
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from alembic.config import Config
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import BACKEND_DIR, Settings
from app.db.session import make_engine, make_session_factory, utcnow
from app.modules.identity.models.user import User
from app.modules.identity.services.auth_service import passwords
from app.modules.posts.models.post import Category, Post
from app.modules.posts.services.catalog import HOTSPOT_ZONES
from app.modules.posts.services.listings import update_search_text

# Synthetic seed sites, used only on the isolated demo database.
SITES = (
    ("LIBRARY", "VN-HN", 21.021, 105.809, 42),
    ("CAFETERIA", "VN-HN", 21.029, 105.819, 34),
    ("PARKING", "VN-SG", 10.771, 106.690, 27),
    ("CLASSROOM", "VN-SG", 10.783, 106.708, 25),
    ("SPORTS", "VN-DN", 16.064, 108.212, 23),
    ("DORMITORY", "VN-DN", 16.077, 108.222, 18),
)
REPORTS = sum(site[-1] for site in SITES) + 15
ITEMS = {
    "ví": "Ví và túi xách",
    "điện thoại": "Thiết bị điện tử",
    "chìa khóa": "Chìa khóa",
    "thẻ sinh viên": "Giấy tờ",
    "túi": "Ví và túi xách",
    "bình nước": "Khác",
}


def demo_id(kind: str, index: int):
    return uuid5(NAMESPACE_URL, f"findback.hotspot-demo.v1/{kind}/{index}")


def demo_engine(settings: Settings):
    url = make_url(settings.database_url)
    if (
        settings.app_env != "hotspot-demo"
        or url.drivername != "sqlite"
        or not url.database
        or Path(url.database).resolve().name != "findback-hotspot-demo.db"
    ):
        raise SystemExit("Use APP_ENV=hotspot-demo and a dedicated findback-hotspot-demo.db")
    return make_engine(settings)


def seed(db, password: str):
    hashed = passwords.hash(password)
    for index in range(28):
        user_id = demo_id("user", index)
        user = db.get(User, user_id)
        if user is None:
            user = User(id=user_id)
            db.add(user)
        if index < 2:
            user.role = "ADMIN" if index == 0 else "USER"
            label = "admin" if index == 0 else "user"
            user.email = f"hotspot-{label}@example.org"
            user.full_name = f"DEMO Hotspot {label}"
            user.password_hash = hashed
    db.flush()
    categories = dict(db.execute(select(Category.name, Category.id)).tuples().all())
    rng = random.Random(60217)
    now = utcnow()
    groups = tuple(
        (zone, region, lat, lon) for zone, region, lat, lon, count in SITES for _ in range(count)
    )
    seen = set(
        db.scalars(
            select(Post.id).where(Post.id.in_([demo_id("post", index) for index in range(REPORTS)]))
        )
    )
    for index in range(REPORTS):
        if index < len(groups):
            zone, region, lat, lon = groups[index]
            lat += rng.choice((-0.001, 0, 0.001))
            lon += rng.choice((-0.001, 0, 0.001))
        else:
            zone, region, lat, lon = "OTHER", "OTHER", 11.2 + (index - len(groups)) * 0.18, 108.1
        days = rng.randrange(31, 59) if index % 4 == 0 else rng.randrange(1, 29)
        time = (now - timedelta(days=days)).replace(
            hour=rng.choice([3, 5, 5, 6, 7, 10]), minute=rng.randrange(60), second=0, microsecond=0
        )
        item = rng.choice(tuple(ITEMS))
        post_id = demo_id("post", index)
        if post_id in seen:
            continue
        post = Post(
            id=post_id,
            owner_id=demo_id("user", index % 28),
            type="LOST",
            status="CLOSED" if index % 9 == 0 else "OPEN",
            title=f"[DEMO] Thất lạc {item} tại {HOTSPOT_ZONES[zone].lower()} ({index + 1})",
            item_name=item,
            description="Dữ liệu giả lập dùng để kiểm thử FindBack Hotspot Analysis.",
            location=f"[DEMO] {HOTSPOT_ZONES[zone]}",
            location_code=region,
            latitude=round(lat, 3),
            longitude=round(lon, 3),
            hotspot_zone=zone,
            event_time=time,
            category_id=categories[ITEMS[item]],
        )
        update_search_text(post)
        db.add(post)
    db.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "delete"))
    args = parser.parse_args()
    settings = Settings()
    engine = demo_engine(settings)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with make_session_factory(engine)() as db:
            if args.action == "create":
                password = os.environ.get("HOTSPOT_DEMO_PASSWORD", "")
                if len(password) < 12:
                    raise SystemExit("Set HOTSPOT_DEMO_PASSWORD to at least 12 characters")
                seed(db, password)
                print(f"Ready: {REPORTS} fictional hotspot reports")
            else:
                ids = [demo_id("post", index) for index in range(REPORTS)]
                removed = db.execute(delete(Post).where(Post.id.in_(ids))).rowcount
                db.commit()
                print(f"Removed {removed} fictional hotspot reports")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
