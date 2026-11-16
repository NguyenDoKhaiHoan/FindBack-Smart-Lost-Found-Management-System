"""Create fictional local records and write short-lived JWTs to a gitignored file."""

import json
from uuid import NAMESPACE_URL, uuid5

from app.core.config import BACKEND_DIR, Settings
from app.core.security import create_access_token
from app.db import models  # noqa: F401
from app.db.session import make_engine, make_session_factory
from app.modules.identity.models.user import User
from app.modules.posts.models.post import Post


def main():
    settings = Settings()
    if settings.app_env != "development":
        raise SystemExit("Demo seeding is only available with APP_ENV=development")
    engine = make_engine(settings)
    demo = {"url": "http://127.0.0.1:8000/docs", "users": {}, "posts": {}}
    with make_session_factory(engine)() as session:
        for name in ("owner", "claimant", "outsider", "admin"):
            user_id = uuid5(NAMESPACE_URL, f"findback-demo/{name}")
            user = session.get(User, user_id)
            if user is None:
                user = User(
                    id=user_id,
                    is_active=True,
                    token_version=1,
                    role="ADMIN" if name == "admin" else "USER",
                )
                session.add(user)
                session.flush()
            demo["users"][name] = {"id": str(user.id), "token": create_access_token(user, settings)}
        owner_id = uuid5(NAMESPACE_URL, "findback-demo/owner")
        for name, post_type in (("found", "FOUND"), ("lost", "LOST")):
            post_id = uuid5(NAMESPACE_URL, f"findback-demo/{name}")
            if session.get(Post, post_id) is None:
                session.add(
                    Post(
                        id=post_id,
                        owner_id=owner_id,
                        type=post_type,
                        status="OPEN",
                        is_hidden=False,
                    )
                )
            demo["posts"][name] = str(post_id)
        session.commit()
    demo["create_body"] = {
        "found_post_id": demo["posts"]["found"],
        "evidence_description": "Du lieu gia lap: mat trong co ky hieu DEMO-123.",
    }
    destination = BACKEND_DIR / ".local" / "claims-demo.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(demo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fictional demo IDs and one-hour JWTs saved to {destination}")
    engine.dispose()


if __name__ == "__main__":
    main()
