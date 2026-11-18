"""rules-v1-draft. Pure public-data scoring; no persistence or ownership decisions."""

import unicodedata
from dataclasses import dataclass
from fractions import Fraction
from uuid import UUID, uuid5

from ..schemas.contracts import PublicPostInput, ScoreDetails

RULE_VERSION = "rules-v1-draft"
STOP_WORDS = frozenset("tôi mình bị mất nhặt được tìm thấy ở tại và là của một cái chiếc".split())
MATCH_NAMESPACE = UUID("1aef93ac-4ba7-4558-bda2-16344077d07a")


def tokens(text: str) -> frozenset[str]:
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(" " if unicodedata.category(char).startswith("P") else char for char in text)
    return frozenset(text.split()) - STOP_WORDS


def rounded(value: Fraction) -> float:
    """Exact nonnegative rational ROUND_HALF_UP to cents; no intermediate rounding."""
    cents = (value.numerator * 200 + value.denominator) // (2 * value.denominator)
    return cents / 100


def eligible(record: PublicPostInput) -> bool:
    return record.is_public and record.matching_eligible and record.post.status == "OPEN"


@dataclass(frozen=True)
class ScoredPair:
    id: UUID
    lost_post_id: UUID
    found_post_id: UUID
    score: float
    details: ScoreDetails
    explanation: str
    delta_microseconds: int


def score_pair(first: PublicPostInput, second: PublicPostInput) -> ScoredPair | None:
    if first.post.id == second.post.id or first.post.type == second.post.type:
        return None
    if not eligible(first) or not eligible(second):
        return None
    lost, found = (
        (first.post, second.post) if first.post.type == "LOST" else (second.post, first.post)
    )
    delta = found.event_time - lost.event_time
    micros = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    seconds = Fraction(micros, 1_000_000)
    if 0 <= seconds <= 86400:
        time_points, time_reason = 20, "within_1_day"
    elif 86400 < seconds <= 3 * 86400:
        time_points, time_reason = 15, "within_3_days"
    elif 3 * 86400 < seconds <= 7 * 86400:
        time_points, time_reason = 5, "within_7_days"
    else:
        time_points, time_reason = 0, "out_of_window"

    a, b = (
        tokens(lost.title + " " + lost.description),
        tokens(found.title + " " + found.description),
    )
    intersection, union = len(a & b), len(a | b)
    keyword_points = Fraction(10 * intersection, union) if a and b else Fraction(0)
    common = lost.public_attributes.keys() & found.public_attributes.keys()
    matched = sum(lost.public_attributes[key] == found.public_attributes[key] for key in common)
    attribute_points = Fraction(10 * matched, len(common)) if common else Fraction(0)
    category_points = 25 if lost.category.id == found.category.id else 0
    location_points = 25 if lost.location.code == found.location.code else 0
    color_missing = lost.color_code is None or found.color_code is None
    color_points = 10 if not color_missing and lost.color_code == found.color_code else 0

    def criterion(points, maximum, missing=False):
        return {
            "points": rounded(Fraction(points)),
            "max_points": maximum,
            "reason": "missing" if missing else "matched" if points else "different",
        }

    details = ScoreDetails.model_validate(
        {
            "category": criterion(category_points, 25),
            "location": criterion(location_points, 25),
            "time": {
                "points": time_points,
                "max_points": 20,
                "reason": time_reason,
                "delta_seconds": float(seconds),
            },
            "color": criterion(color_points, 10, color_missing),
            "keywords": {
                **criterion(keyword_points, 10, not a or not b),
                "intersection_count": intersection,
                "union_count": union,
            },
            "public_attributes": {
                **criterion(attribute_points, 10, not common),
                "matched_count": matched,
                "compared_count": len(common),
            },
        }
    )
    total = rounded(
        Fraction(category_points + location_points + time_points + color_points)
        + keyword_points
        + attribute_points
    )
    labels = {
        "category": "Danh mục",
        "location": "Khu vực",
        "time": "Thời gian",
        "color": "Màu",
        "keywords": "Từ khóa",
        "public_attributes": "Thuộc tính công khai",
    }
    reasons = {
        "matched": "có phần khớp",
        "different": "khác nhau",
        "missing": "thiếu dữ liệu so sánh",
        "within_1_day": "trong 1 ngày",
        "within_3_days": "trong 3 ngày",
        "within_7_days": "trong 7 ngày",
        "out_of_window": "ngoài khoảng thời gian",
    }
    explanation = "; ".join(
        f"{labels[key]}: {reasons[value.reason]} (+{value.points:g})"
        for key, value in ((key, getattr(details, key)) for key in labels)
    )
    explanation += ". Đây là gợi ý, cần xác minh qua claim."
    return ScoredPair(
        uuid5(MATCH_NAMESPACE, f"{lost.id}:{found.id}"),
        lost.id,
        found.id,
        total,
        details,
        explanation,
        micros,
    )


def rank_candidates(source: PublicPostInput, candidates: list[PublicPostInput]) -> list[ScoredPair]:
    """Deduplicate IDs and sort before pagination. Threshold uses rounded total."""
    unique = {candidate.post.id: candidate for candidate in candidates}
    pairs = [
        pair
        for candidate in unique.values()
        if (pair := score_pair(source, candidate)) is not None and pair.score >= 50
    ]

    def key(pair):
        candidate_id = pair.found_post_id if source.post.type == "LOST" else pair.lost_post_id
        return (-pair.score, abs(pair.delta_microseconds), candidate_id.int)

    return sorted(pairs, key=key)
