from datetime import datetime
from uuid import UUID

import pytest

from app.modules.matching.schemas.contracts import PublicPost, PublicPostInput


@pytest.fixture
def make_post():
    def make(number=1, type="LOST", **changes):
        policy = {key: changes.pop(key) for key in ("is_public", "matching_eligible") if key in changes}
        data = {
            "id": UUID(int=number), "type": type, "title": "ví gấp", "description": "ví gấp",
            "category": {"id": UUID(int=100), "name": "Ví"},
            "location": {"code": "AREA_A", "name": "Khu A"},
            "event_time": datetime.fromisoformat("2026-11-10T08:00:00+07:00"),
            "created_at": datetime.fromisoformat("2026-11-10T09:00:00+07:00"),
            "status": "OPEN", "color_code": "BLACK",
            "public_attributes": {"brand": "demo-a", "material": "da"},
        }
        if type == "FOUND":
            data["event_time"] = datetime.fromisoformat("2026-11-10T12:00:00+07:00")
        return PublicPostInput(post=PublicPost.model_validate({**data, **changes}),
                               **{"is_public": True, "matching_eligible": True, **policy})
    return make
