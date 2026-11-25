"""Precompute embeddings for visible open posts and their images."""

from app.core.config import Settings
from app.db import models  # noqa: F401
from app.db.session import make_engine, make_session_factory
from app.modules.ai.images import image_embeddings
from app.modules.ai.matching import open_posts, text_embeddings, with_text_cache
from app.modules.ai.runtime import AIRuntime
from app.modules.posts.models.post import Post


def main():
    settings = Settings()
    runtime = AIRuntime(settings)
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    try:
        if settings.ai_matching_enabled and runtime.text_backend != "details":
            pending = True
            while pending:
                with factory() as db:
                    posts = list(db.scalars(with_text_cache(open_posts().order_by(Post.id))))
                    _, pending = text_embeddings(db, runtime, posts)
            print("Text index is up to date.")
        if settings.ai_image_search_enabled:
            pending = True
            while pending:
                with factory() as db:
                    _, _, pending = image_embeddings(db, runtime, open_posts())
            print("Image index is up to date.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
