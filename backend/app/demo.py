"""Explicit fake-data demo: uvicorn app.demo:create_demo_app --factory."""
from .main import create_app
from .modules.matching.repositories.snapshots import MemoryMatchingStore
from .modules.matching.schemas.contracts import PublicPost, PublicPostInput

SOURCE_ID = "10000000-0000-4000-8000-000000000001"


def create_demo_app():
    common = {
        "title": "ví gấp", "description": "ví gấp",
        "category": {"id": "30000000-0000-4000-8000-000000000001", "name": "Ví"},
        "location": {"code": "AREA_A", "name": "Khu A"},
        "status": "OPEN", "color_code": "BLACK",
        "public_attributes": {"brand": "demo-a", "material": "da"},
        "created_at": "2026-11-10T06:00:00Z",
    }
    source = PublicPostInput(
        post=PublicPost.model_validate({**common, "id": SOURCE_ID, "type": "LOST", "event_time": "2026-11-10T01:00:00Z"}),
        is_public=True, matching_eligible=True,
    )
    candidate = PublicPostInput(
        post=PublicPost.model_validate({**common, "id": "20000000-0000-4000-8000-000000000001", "type": "FOUND", "event_time": "2026-11-10T05:00:00Z"}),
        is_public=True, matching_eligible=True,
    )
    store = MemoryMatchingStore([source, candidate])
    store.recalculate(source.post.id)
    store.recalculate(candidate.post.id)
    return create_app(store)
