from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from pydantic import Field
from sqlalchemy.orm import Session, selectinload

from app.modules.ai.chat_guard import normalized_question, redact_sensitive_text
from app.modules.ai.matching import open_posts
from app.modules.ai.schemas import AIInput, ChatItem, ChatMap, ChatResult
from app.modules.posts.models.post import Post
from app.modules.posts.services.catalog import LOCATIONS

# GeoNames reference points for the three FindBack city filters.
CITY_COORDINATES = {
    "VN-HN": (21.0245, 105.84117),
    "VN-SG": (10.82302, 106.62965),
    "VN-DN": (16.068, 108.221),
}
CITY_ALIASES = {
    "ha noi": "VN-HN",
    "hanoi": "VN-HN",
    "hn": "VN-HN",
    "ho chi minh": "VN-SG",
    "thanh pho ho chi minh": "VN-SG",
    "tp ho chi minh": "VN-SG",
    "tp hcm": "VN-SG",
    "tphcm": "VN-SG",
    "hcm": "VN-SG",
    "sai gon": "VN-SG",
    "da nang": "VN-DN",
    "danang": "VN-DN",
}


class DirectionsArgs(AIInput):
    origin: str | None = Field(min_length=2, max_length=120)
    destination: str | None = Field(min_length=2, max_length=120)


@dataclass(frozen=True)
class Place:
    address: str
    city: str | None
    coordinates: tuple[float, float] | None
    posts: tuple[Post, ...] = ()


def safe_map_place(text: str) -> str | None:
    cleaned = redact_sensitive_text(text)
    return cleaned if cleaned == text and "://" not in text else None


def public_posts_at(db: Session, place: str) -> list[Post]:
    return list(
        db.scalars(
            open_posts()
            .where(Post.location.icontains(place, autoescape=True))
            .options(selectinload(Post.images))
            .order_by(Post.created_at.desc(), Post.id)
            .limit(12)
        )
    )


def resolve_place(db: Session, name: str) -> list[Place]:
    city = CITY_ALIASES.get(normalized_question(name))
    if city:
        return [Place(LOCATIONS[city], city, CITY_COORDINATES[city])]

    groups = {}
    for post in public_posts_at(db, name):
        if post.location and (address := safe_map_place(post.location)):
            groups.setdefault(address, []).append(post)

    places = []
    for address, posts in groups.items():
        cities = {post.location_code for post in posts if post.location_code in CITY_COORDINATES}
        points = {
            (float(post.latitude), float(post.longitude))
            for post in posts
            if post.latitude is not None and post.longitude is not None
        }
        places.append(
            Place(
                address,
                next(iter(cities)) if len(cities) == 1 else None,
                next(iter(points)) if len(points) == 1 else None,
                tuple(posts),
            )
        )
    return places


def distance_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    lat1, lon1 = map(radians, origin)
    lat2, lon2 = map(radians, destination)
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(min(h, 1.0)))


def formatted_distance(km: float) -> str:
    if km < 1:
        return f"{round(km * 1000)} m"
    if km < 20:
        return f"{km:.1f}".replace(".", ",") + " km"
    return f"{round(km):,}".replace(",", ".") + " km"


def directions(db: Session, args: DirectionsArgs) -> ChatResult:
    if not args.origin or not args.destination:
        return ChatResult(reply="Bạn cho mình điểm xuất phát và nơi muốn đến nhé.")

    origins = resolve_place(db, args.origin)
    destinations = resolve_place(db, args.destination)
    if not origins or not destinations:
        missing = args.origin if not origins else args.destination
        return ChatResult(
            reply=f"Mình chưa xác định được “{missing}” từ các tin công khai hoặc khu vực "
            "FindBack hỗ trợ. Bạn cho mình tên thành phố hoặc địa chỉ ghi trong tin nhé."
        )
    if len(origins) > 1 or len(destinations) > 1:
        choices = origins if len(origins) > 1 else destinations
        label = "điểm xuất phát" if len(origins) > 1 else "điểm đến"
        return ChatResult(
            reply=f"Mình tìm thấy nhiều địa chỉ cho {label}. Bạn cho mình thêm quận hoặc "
            "tên địa danh cụ thể nhé.",
            related_items=[ChatItem.from_post(place.posts[0]) for place in choices[:4]],
        )

    origin, destination = origins[0], destinations[0]
    if origin.address == destination.address:
        return ChatResult(reply=f"Hai địa điểm bạn hỏi đều là “{destination.address}”.")

    if origin.coordinates is not None and destination.coordinates is not None:
        distance = formatted_distance(distance_km(origin.coordinates, destination.coordinates))
        detail = f"Khoảng {distance} theo đường chim bay giữa hai mốc địa điểm."
    elif (
        origin.city in CITY_COORDINATES
        and destination.city in CITY_COORDINATES
        and origin.city != destination.city
    ):
        distance = formatted_distance(
            distance_km(CITY_COORDINATES[origin.city], CITY_COORDINATES[destination.city])
        )
        detail = (
            f"Từ trung tâm {LOCATIONS[origin.city]} đến trung tâm "
            f"{LOCATIONS[destination.city]} khoảng {distance} theo đường chim bay."
        )
    else:
        detail = "Bạn có thể mở chỉ đường để xem quãng đường di chuyển giữa hai địa điểm."

    return ChatResult(
        reply=f"Điểm đến tìm được là “{destination.address}”. {detail}",
        map_place=ChatMap(origin=origin.address, destination=destination.address),
        related_items=[ChatItem.from_post(post) for post in destination.posts[:3]],
    )
