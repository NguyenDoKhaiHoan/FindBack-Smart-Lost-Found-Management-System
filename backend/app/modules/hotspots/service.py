from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from threading import Lock
from time import monotonic
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.session import utcnow
from app.modules.ai.chat_guard import redact_sensitive_text
from app.modules.hotspots.clustering import (
    Coordinate,
    center,
    cluster_labels,
    previous_cluster_members,
)
from app.modules.hotspots.models import HotspotSettings
from app.modules.hotspots.schemas import (
    AlgorithmConfig,
    Analysis,
    Cluster,
    ClusterDetail,
    ConfigPatch,
    Count,
    Density,
    GroupBy,
    HeatPoint,
    HotspotQuery,
    RelatedPost,
    Scope,
    Statistics,
    Trend,
    Window,
)
from app.modules.posts.models.post import Category, Post
from app.modules.posts.services.catalog import HOTSPOT_ZONES, LOCATIONS
from app.shared.errors import DomainError

LOCAL_TZ = timezone(timedelta(hours=7))
PUBLIC_MIN_REPORTERS = 5
MAX_EVENTS_PER_PERIOD = 6000
MAX_CLUSTERS = 100
CACHE_SECONDS = 90
CACHE_ENTRIES = 24


@dataclass(frozen=True)
class Event:
    id: UUID
    reporter: UUID
    title: str
    time: datetime
    coordinate: Coordinate
    category: str
    region: str
    zone: str

    @property
    def area(self):
        return f"{HOTSPOT_ZONES[self.zone]} · {LOCATIONS[self.region]}"

    @property
    def hour(self):
        start = self.time.hour // 2 * 2
        return f"{start:02}:00–{start + 2:02}:00"


@dataclass(frozen=True)
class Snapshot:
    analysis: Analysis
    related: dict[str, list[RelatedPost]]

    def detail(self, cluster_id: str) -> ClusterDetail:
        cluster = next(
            (cluster for cluster in self.analysis.clusters if cluster.cluster_id == cluster_id),
            None,
        )
        if cluster is None:
            raise DomainError(404, "HOTSPOT_NOT_FOUND", "No hotspot matches the current filters")
        return ClusterDetail(**cluster.model_dump(), related_posts=self.related[cluster_id])


def density_level(count: int, config: AlgorithmConfig) -> Density:
    if count >= config.very_high_count:
        return "very_high"
    if count >= config.high_count:
        return "high"
    if count >= config.medium_count:
        return "medium"
    return "low"


def ranked(counter: Counter, limit: int = 10, minimum: int = 1) -> list[Count]:
    pairs = ((label, count) for label, count in counter.items() if count >= minimum)
    return [
        Count(label=label, count=count)
        for label, count in sorted(pairs, key=lambda pair: (-pair[1], pair[0]))[:limit]
    ]


def bucket(day: date, group_by: GroupBy) -> date:
    if group_by == "week":
        return day - timedelta(days=day.weekday())
    if group_by == "month":
        return day.replace(day=1)
    return day


def series(events: list[Event], window: Window, group_by: GroupBy) -> list[Count]:
    days = (
        window.start_date + timedelta(days=offset)
        for offset in range((window.end_date - window.start_date).days + 1)
    )
    counts = dict.fromkeys((bucket(day, group_by) for day in days), 0)
    counts.update(Counter(bucket(event.time.date(), group_by) for event in events))
    return [Count(label=day.isoformat(), count=count) for day, count in sorted(counts.items())]


def trend(current: int, previous: int) -> Trend | None:
    if min(current, previous) < 5:
        return None
    return Trend(
        previous_count=previous, change_percent=round(100 * (current - previous) / previous, 1)
    )


def coordinate(latitude, longitude) -> Coordinate | None:
    if latitude is None or longitude is None:
        return None
    point = float(latitude), float(longitude)
    if not (-90 <= point[0] <= 90 and -180 <= point[1] <= 180) or point == (0, 0):
        return None
    return point


def to_events(rows) -> list[Event]:
    events, seen = [], set()
    for row in rows:
        point = coordinate(row.latitude, row.longitude)
        if point is None or row.hotspot_zone not in HOTSPOT_ZONES:
            continue
        occurred = row.event_time.astimezone(LOCAL_TZ)
        key = (
            row.owner_id,
            occurred.replace(second=0, microsecond=0),
            row.category_id,
            row.hotspot_zone,
            row.location_code,
            point,
            " ".join((row.title or "").casefold().split()),
            " ".join((row.item_name or "").casefold().split()),
        )
        if key in seen:
            continue
        seen.add(key)
        events.append(
            Event(
                row.id,
                row.owner_id,
                row.title or "Tin thất lạc",
                occurred,
                point,
                row.category or "Chưa phân loại",
                row.location_code if row.location_code in LOCATIONS else "OTHER",
                row.hotspot_zone,
            )
        )
    return events


def query_windows(filters: HotspotQuery, config: AlgorithmConfig, now: datetime):
    if filters.start_date is not None and filters.end_date is not None:
        start, end = filters.start_date, filters.end_date
    else:
        end = now.astimezone(LOCAL_TZ).date()
        days = int(filters.period) if filters.period else config.period_days
        start = end - timedelta(days=days - 1)
    return (
        Window(start_date=start, end_date=end),
        Window(
            start_date=start - (end - start + timedelta(days=1)), end_date=start - timedelta(days=1)
        ),
    )


def day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, LOCAL_TZ).astimezone(timezone.utc)


def build_snapshot(
    current: list[Event],
    previous: list[Event],
    config: AlgorithmConfig,
    filters: HotspotQuery,
    windows: tuple[Window, Window],
    scope: Scope,
    demo: bool,
    truncated: bool,
) -> Snapshot:
    window, previous_window = windows
    public = scope == "public"
    points = [event.coordinate for event in current]
    minimum = max(PUBLIC_MIN_REPORTERS, config.min_samples) if public else config.min_samples
    labels = cluster_labels(points, config.eps_meters, minimum)
    grouped = defaultdict(list)
    for event, label in zip(current, labels, strict=True):
        if label != -1:
            grouped[label].append(event)
    groups = sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    if public:
        groups = [
            (label, group)
            for label, group in groups
            if len({event.reporter for event in group}) >= PUBLIC_MIN_REPORTERS
        ]
    previous_matches = (
        {}
        if public
        else previous_cluster_members(
            points, labels, [event.coordinate for event in previous], config.eps_meters
        )
    )

    clusters, related = [], {}
    visible_events = [event for _, group in groups for event in group] if public else current
    for label, group in groups[:MAX_CLUSTERS]:
        key = sha256(b"".join(sorted(event.id.bytes for event in group))).hexdigest()[:24]
        latitude, longitude = center([event.coordinate for event in group], 2 if public else 3)
        areas = ranked(Counter(event.area for event in group), 1)
        hours = ranked(Counter(event.hour for event in group), 1, 3 if public else 1)
        clusters.append(
            Cluster(
                cluster_id=key,
                location_name=areas[0].label,
                latitude=latitude,
                longitude=longitude,
                event_count=len(group),
                density_level=density_level(len(group), config),
                top_categories=ranked(
                    Counter(event.category for event in group), 4, 3 if public else 1
                ),
                peak_time=hours[0] if hours else None,
                timeline=[] if public else series(group, window, filters.group_by),
                trend=None
                if public or truncated
                else trend(len(group), len(previous_matches.get(label, []))),
            )
        )
        related[key] = [
            RelatedPost(
                id=event.id, title=redact_sensitive_text(event.title), event_day=event.time.date()
            )
            for event in group[:12]
        ]
    stats = Statistics(
        total_events=len(visible_events),
        total_hotspots=len(groups),
        high_density_areas=sum(
            density_level(len(group), config) in ("high", "very_high") for _, group in groups
        ),
        noise_events=None if public else labels.count(-1),
        top_areas=ranked(Counter(event.area for event in visible_events), 5, 3 if public else 1),
        categories=ranked(
            Counter(event.category for event in visible_events), minimum=3 if public else 1
        ),
        hours=ranked(Counter(event.hour for event in visible_events), 12, 3 if public else 1),
        regions=ranked(
            Counter(LOCATIONS[event.region] for event in visible_events), minimum=3 if public else 1
        ),
        timeline=[] if public else series(visible_events, window, filters.group_by),
        trend=None if public or truncated else trend(len(current), len(previous)),
    )
    insights = []
    if stats.top_areas:
        area = stats.top_areas[0]
        insights.append(f"{area.label} có {area.count} báo cáo trong kỳ đã chọn.")
    if stats.hours:
        hour = stats.hours[0]
        insights.append(f"Khung {hour.label} ghi nhận nhiều nhất với {hour.count} báo cáo.")
    if stats.categories:
        category = stats.categories[0]
        insights.append(f"Danh mục {category.label} có {category.count} báo cáo trong kỳ.")
    if stats.top_areas and not public:
        insights.append(
            "Có thể bố trí nhắc kiểm tra tư trang tại khu vực có nhiều báo cáo "
            "và theo dõi ở kỳ tiếp theo."
        )
    return Snapshot(
        Analysis(
            period=window,
            previous_period=previous_window,
            is_demo=demo,
            truncated=truncated or len(groups) > MAX_CLUSTERS,
            statistics=stats,
            clusters=clusters,
            heatmap=[HeatPoint.model_validate(cluster.model_dump()) for cluster in clusters],
            insights=insights,
        ),
        related,
    )


class HotspotService:
    def __init__(self, *, demo: bool = False):
        self.demo = demo
        self.lock = Lock()
        self.compute = Lock()
        self.cache: OrderedDict[tuple, tuple[float, Snapshot]] = OrderedDict()

    def config(self, db: Session) -> AlgorithmConfig:
        return AlgorithmConfig.model_validate(db.get(HotspotSettings, 1))

    def update(self, db: Session, payload: ConfigPatch) -> AlgorithmConfig:
        if db.get_bind().dialect.name == "sqlite":
            # SQLite ignores FOR UPDATE. Take its writer lock before merging settings.
            db.execute(update(HotspotSettings).where(HotspotSettings.id == 1).values(id=1))
        row = db.scalar(select(HotspotSettings).where(HotspotSettings.id == 1).with_for_update())
        existing = AlgorithmConfig.model_validate(row)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise DomainError(422, "INVALID_HOTSPOT_CONFIG", "Provide at least one setting")
        try:
            config = AlgorithmConfig.model_validate({**existing.model_dump(), **changes})
        except ValidationError as exc:
            raise DomainError(422, "INVALID_HOTSPOT_CONFIG", exc.errors()[0]["msg"]) from None
        for key, value in config.model_dump().items():
            setattr(row, key, value)
        db.commit()
        with self.lock:
            self.cache.clear()
        return config

    def analyze(
        self, db: Session, filters: HotspotQuery, scope: Scope, *, force: bool = False
    ) -> Snapshot:
        now = utcnow()
        config = self.config(db)
        windows = query_windows(filters, config, now)
        window, previous = windows
        start = day_start(window.start_date)
        bounds = (
            Post.type == "LOST",
            Post.is_hidden.is_(False),
            Post.deleted_at.is_(None),
            Post.hotspot_zone.is_not(None),
            Post.latitude.is_not(None),
            Post.longitude.is_not(None),
            Post.event_time >= day_start(previous.start_date)
            if scope == "admin"
            else Post.event_time >= start,
            Post.event_time < day_start(window.end_date + timedelta(days=1)),
            Post.event_time <= now,
        )
        for value, field in (
            (filters.category_id, Post.category_id),
            (filters.location_id, Post.location_code),
            (filters.zone, Post.hotspot_zone),
        ):
            if value is not None:
                bounds += (field == value,)

        signature = tuple(
            db.execute(select(func.count(), func.max(Post.updated_at)).where(*bounds)).one()
        )
        key = (
            scope,
            tuple(filters.model_dump().values()),
            window.start_date,
            window.end_date,
            tuple(config.model_dump().values()),
            signature,
        )
        with self.lock:
            if (
                not force
                and (entry := self.cache.get(key))
                and monotonic() - entry[0] < CACHE_SECONDS
            ):
                self.cache.move_to_end(key)
                return entry[1]
            if force:
                self.cache.clear()

        query = (
            select(
                Post.id,
                Post.owner_id,
                Post.title,
                Post.item_name,
                Post.hotspot_zone,
                Post.latitude,
                Post.longitude,
                Post.event_time,
                Post.category_id,
                Post.location_code,
                Category.name.label("category"),
            )
            .outerjoin(Category, Category.id == Post.category_id)
            .where(*bounds)
            .order_by(Post.event_time.desc(), Post.created_at.asc(), Post.id)
        )
        current = db.execute(
            query.where(Post.event_time >= start).limit(MAX_EVENTS_PER_PERIOD + 1)
        ).all()
        historic = (
            db.execute(query.where(Post.event_time < start).limit(MAX_EVENTS_PER_PERIOD + 1)).all()
            if scope == "admin"
            else []
        )
        db.commit()
        truncated = max(len(current), len(historic)) > MAX_EVENTS_PER_PERIOD
        if not self.compute.acquire(timeout=2):
            raise DomainError(503, "HOTSPOT_BUSY", "Hotspot analysis is busy")
        try:
            with self.lock:
                if (
                    not force
                    and (entry := self.cache.get(key))
                    and (monotonic() - entry[0] < CACHE_SECONDS)
                ):
                    return entry[1]
            snapshot = build_snapshot(
                to_events(current[:MAX_EVENTS_PER_PERIOD]),
                to_events(historic[:MAX_EVENTS_PER_PERIOD]),
                config,
                filters,
                windows,
                scope,
                self.demo,
                truncated,
            )
            with self.lock:
                self.cache[key] = monotonic(), snapshot
                self.cache.move_to_end(key)
                while len(self.cache) > CACHE_ENTRIES:
                    self.cache.popitem(last=False)
        finally:
            self.compute.release()
        return snapshot
