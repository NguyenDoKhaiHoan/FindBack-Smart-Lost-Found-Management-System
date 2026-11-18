"""Start the real backend against disposable SQLite fixtures for frontend HTTP tests.

The single stdout record is a private child-process pipe consumed by the Node
harness. It is never logged or written to disk. No application .env is loaded.
"""

import json
import secrets
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "backend"))

from app.core.config import Settings  # noqa: E402
from app.db.session import make_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.conftest import migrate, populate  # noqa: E402
from tests.decision_helpers import ready  # noqa: E402


def main():
    temporary_root = (REPOSITORY / "frontend" / ".local").resolve()
    temporary_root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="live-api-", dir=temporary_root)).resolve()
    engine = None
    server = None
    thread = None
    try:
        settings = Settings(
            _env_file=None,
            database_url=f"sqlite:///{(directory / 'claims.db').as_posix()}",
            database_schema="findback_api",
            jwt_secret_key=secrets.token_urlsafe(48),
            media_root=directory / "uploads",
            app_env="test",
        )
        engine = make_engine(settings)
        migrate(engine)
        world = populate(settings, engine)
        app = create_app(settings, engine=engine)
        # Keep the pre-arranged case for the claims-only regression suite.
        # Browser E2E tests exercise the handover API on newly registered accounts.
        with TestClient(app) as client:
            world.client = client
            prepared_id, prepared_version = ready(world)
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=18000, access_log=False, log_level="error",
        ))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 15
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Isolated test backend could not start on port 18000")
            time.sleep(0.05)
        print(json.dumps({
            "ids": {name: str(value) for name, value in world.ids.items()},
            "tokens": world.tokens,
            "prepared_claim": str(prepared_id),
            "prepared_version": prepared_version,
        }), flush=True)
        sys.stdin.readline()
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=10)
        if engine:
            engine.dispose()
        # Verify the absolute cleanup target before recursive removal on Windows.
        if directory.is_relative_to(temporary_root) and directory.name.startswith("live-api-"):
            shutil.rmtree(directory)


if __name__ == "__main__":
    main()
