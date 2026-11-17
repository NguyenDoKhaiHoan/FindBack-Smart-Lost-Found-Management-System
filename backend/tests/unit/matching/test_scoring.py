from datetime import timedelta
from fractions import Fraction
import unicodedata
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.matching.schemas.contracts import PublicPost
from app.modules.matching.services.scoring import rank_candidates, rounded, score_pair, tokens


def test_documented_examples_a_to_d(make_post):
    lost = make_post()
    full = make_post(2, "FOUND")
    unrelated = make_post(3, "FOUND", category={"id": UUID(int=101), "name": "Tai nghe"},
                          location={"code": "AREA_B", "name": "Khu B"},
                          event_time=lost.post.event_time + timedelta(days=10), color_code="WHITE",
                          title="tai nghe", description="tai nghe", public_attributes={"brand": "demo-b", "material": "nhựa"})
    missing = make_post(4, "FOUND", color_code=None)
    partial = make_post(5, "FOUND", location={"code": "AREA_B", "name": "Khu B"},
                        event_time=lost.post.event_time + timedelta(days=2), title="ví gấp khóa", description="ví gấp khóa",
                        public_attributes={"brand": "demo-a", "material": "vải"})
    assert [score_pair(lost, item).score for item in (full, unrelated, missing, partial)] == [100, 0, 90, 61.67]
    assert score_pair(lost, partial).details.keywords.points == 6.67
    assert [item.score for item in rank_candidates(lost, [partial, unrelated, missing, full])] == [100, 90, 61.67]


@pytest.mark.parametrize("seconds,points", [(0, 20), (86400, 20), (86401, 15), (259200, 15), (259201, 5), (604800, 5), (604801, 0), (-1, 0)])
def test_time_boundaries(make_post, seconds, points):
    lost = make_post()
    found = make_post(2, "FOUND", event_time=lost.post.event_time + timedelta(seconds=seconds))
    assert score_pair(lost, found).details.time.points == points


def test_fractional_second_boundary_and_timezone(make_post):
    lost = make_post()
    found = make_post(2, "FOUND", event_time=lost.post.event_time + timedelta(days=1, microseconds=1))
    assert score_pair(lost, found).details.time.points == 15
    assert found.post.event_time.utcoffset() == timedelta(0)


def test_invalid_pairs_and_policy(make_post):
    source = make_post()
    assert score_pair(source, source) is None
    assert score_pair(source, make_post(2)) is None
    for changes in ({"is_public": False}, {"matching_eligible": False}, {"status": "CLOSED"}):
        assert score_pair(source, make_post(2, "FOUND", **changes)) is None


def test_reverse_direction_and_stable_ties(make_post):
    source = make_post()
    far = make_post(2, "FOUND", event_time=source.post.event_time + timedelta(hours=6))
    near_high_id = make_post(4, "FOUND")
    near_low_id = make_post(3, "FOUND")
    candidates = [far, near_high_id, near_low_id, near_low_id, source]
    ranked = rank_candidates(source, candidates)
    assert [pair.found_post_id.int for pair in ranked] == [3, 4, 2]
    assert ranked == rank_candidates(source, list(reversed(candidates)))
    reverse = score_pair(near_low_id, source)
    assert reverse == score_pair(source, near_low_id)


def test_empty_tokens_and_missing_attributes(make_post):
    lost = make_post(title="Tôi tìm", description="một chiếc!")
    found = make_post(2, "FOUND", public_attributes={"brand": " ", "material": ""})
    result = score_pair(lost, found)
    assert result.details.keywords.reason == "missing"
    assert result.details.keywords.points == 0
    assert result.details.public_attributes.compared_count == 0
    assert result.details.public_attributes.reason == "missing"
    assert tokens(unicodedata.normalize("NFD", "TÌM ví, gấp!")) == {"ví", "gấp"}


def test_one_common_attribute_and_normalization(make_post):
    result = score_pair(make_post(), make_post(2, "FOUND", public_attributes={"brand": "  DEMO-A  "}))
    assert result.details.public_attributes.points == 10
    assert result.details.public_attributes.compared_count == 1


def test_exact_rounding_and_threshold(make_post):
    assert rounded(Fraction(49995, 1000)) == 50
    assert rounded(Fraction(49994, 1000)) == 49.99
    source = make_post()
    # category + location only: 50; missing text signal/color/attributes, time outside window.
    exact = make_post(2, "FOUND", title="tai nghe", description="tai nghe", color_code=None,
                      public_attributes={}, event_time=source.post.event_time + timedelta(days=10))
    assert rank_candidates(source, [exact])[0].score == 50
    different_area = make_post(3, "FOUND", location={"code": "AREA_B", "name": "Khu B"},
                               title="tai nghe", description="tai nghe", color_code=None, public_attributes={},
                               event_time=source.post.event_time + timedelta(days=10))
    assert rank_candidates(source, [different_area]) == []


@pytest.mark.parametrize("change", [{"event_time": None}, {"event_time": "2026-11-10T08:00:00"}, {"description": " "}, {"category": None}, {"public_attributes": {"serial": "SECRET"}}, {"claim_evidence": "SECRET"}])
def test_input_boundary_rejects_incomplete_or_private_fields(make_post, change):
    data = make_post().post.model_dump()
    with pytest.raises(ValidationError):
        PublicPost.model_validate({**data, **change})
