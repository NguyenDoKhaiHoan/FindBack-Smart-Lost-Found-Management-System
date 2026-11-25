from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.modules.ai.inference import cosine_similarity
from app.modules.ai.matching import score_pair
from app.modules.posts.models.post import Post


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ([2.0, 0.0], [3.0, 0.0], 1.0),
        ([1.0, 0.0], [1.0, 1.0], 2**-0.5),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 0.0], [-1.0, 0.0], 0.0),
        ([0.0, 0.0], [1.0, 0.0], 0.0),
        ([], [1.0], 0.0),
        ([1.0, 2.0], [1.0], 0.0),
    ],
)
def test_cosine_for_text_and_image_vectors(first, second, expected):
    assert cosine_similarity(first, second) == pytest.approx(expected)


def pair():
    category = uuid4()
    now = datetime.now(timezone.utc)
    fields = dict(
        status="OPEN",
        category_id=category,
        color_code="BLACK",
        location="Thư viện",
        event_time=now,
        is_hidden=False,
        title="Ví da",
        description=None,
        images=[],
    )
    return Post(id=uuid4(), type="LOST", **fields), Post(id=uuid4(), type="FOUND", **fields)


def test_matching_weights_and_reasons_without_images_or_description():
    lost, found = pair()
    found.color_code = "WHITE"
    found.event_time += timedelta(days=3)
    score, reasons = score_pair(found, lost, 0.8)
    assert score == pytest.approx(0.50 * 0.8 + 0.12 + 0.20 + 0.10 * 0.5)
    assert "Cùng màu sắc" not in reasons
    assert "Cùng danh mục" in reasons
    assert "Tiêu đề hoặc mô tả tương tự" in reasons


def test_missing_fields_are_not_counted_as_matches():
    lost, found = pair()
    lost.category_id = None
    lost.location = None
    lost.event_time = None
    score, reasons = score_pair(lost, found, 0.64)
    assert score == round((0.50 * 0.64 + 0.08) / 0.58, 4)
    assert reasons == ["Tiêu đề hoặc mô tả tương tự", "Cùng màu sắc"]
    assert score_pair(lost, found, None) is None


@pytest.mark.parametrize("change", ["same", "same_type", "hidden", "closed", "reversed_time"])
def test_rejects_ineligible_matches(change):
    lost, found = pair()
    if change == "same":
        found = lost
    elif change == "same_type":
        found.type = "LOST"
    elif change == "hidden":
        found.is_hidden = True
    elif change == "closed":
        found.status = "CLOSED"
    else:
        found.event_time -= timedelta(hours=1)
    assert score_pair(lost, found, 1.0) is None
