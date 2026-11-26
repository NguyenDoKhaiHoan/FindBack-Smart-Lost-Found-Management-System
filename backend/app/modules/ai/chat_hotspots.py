from typing import Literal

from sqlalchemy.orm import Session

from app.modules.ai.schemas import AIInput, ChatResult
from app.modules.hotspots.schemas import HotspotQuery, Scope
from app.modules.hotspots.service import HotspotService
from app.modules.posts.services.catalog import HOTSPOT_ZONES, LOCATIONS, HotspotZone, LocationCode


class HotspotArgs(AIInput):
    period: Literal["7", "30", "90"] | None
    location_id: LocationCode | None
    zone: HotspotZone | None
    unsupported_place: bool
    managed_only: bool


HOTSPOT_TOOLS = {
    "get_lost_item_hotspots": (
        HotspotArgs,
        "Xem các khu vực, điểm nóng có nhiều báo cáo thất lạc.",
    ),
    "get_hotspot_statistics": (HotspotArgs, "Xem tổng số báo cáo thất lạc và số điểm nóng."),
    "get_top_lost_categories": (
        HotspotArgs,
        "Xem các danh mục thường được báo mất trong một khu vực.",
    ),
    "get_peak_lost_hours": (HotspotArgs, "Xem khung giờ có nhiều báo cáo thất lạc nhất."),
}


def hotspot_reply(
    db: Session, service: HotspotService, scope: Scope, name: str, args: HotspotArgs
) -> ChatResult:
    if args.managed_only:
        return ChatResult(
            reply="FindBack hiện chưa có phân quyền theo địa điểm quản lý. Bạn có thể chọn "
            "khu vực và loại địa điểm trên Bản đồ thất lạc.",
            action="hotspots",
        )
    if args.unsupported_place:
        return ChatResult(
            reply="Bản đồ hiện hỗ trợ thống kê theo thành phố và nhóm địa điểm như thư viện, "
            "căn tin, bãi gửi xe. Bạn có thể chọn một nhóm hoặc thành phố để xem.",
            action="hotspots",
        )
    result = service.analyze(
        db, HotspotQuery(period=args.period, location_id=args.location_id, zone=args.zone), scope
    ).analysis
    stats = result.statistics
    where = " · ".join(
        part for part in (LOCATIONS.get(args.location_id), HOTSPOT_ZONES.get(args.zone)) if part
    )
    days = (result.period.end_date - result.period.start_date).days + 1
    prefix = f"{'Dữ liệu giả lập. ' if result.is_demo else ''}Trong {days} ngày qua"
    if where:
        prefix += f" tại {where}"
    if stats.total_events == 0:
        answer = "chưa có đủ báo cáo có vị trí để hiển thị thống kê theo bộ lọc này."
    elif name == "get_lost_item_hotspots":
        places = ", ".join(f"{row.label} ({row.count})" for row in stats.top_areas[:3])
        answer = (
            f"FindBack ghi nhận {stats.total_hotspots} điểm nóng. "
            f"Khu vực có nhiều báo cáo gồm {places}."
        )
    elif name == "get_top_lost_categories":
        top = ", ".join(f"{row.label} ({row.count})" for row in stats.categories[:3])
        answer = (
            f"các danh mục được báo mất nhiều gồm {top}."
            if top
            else "dữ liệu theo danh mục còn ít."
        )
    elif name == "get_peak_lost_hours":
        hour = stats.hours[0] if stats.hours else None
        answer = (
            f"khung {hour.label} (giờ Việt Nam) có nhiều báo cáo nhất với {hour.count}."
            if hour
            else "dữ liệu theo khung giờ còn ít."
        )
    else:
        answer = (
            f"FindBack ghi nhận {stats.total_events} báo cáo trong thống kê "
            f"và {stats.total_hotspots} điểm nóng."
        )
        if stats.top_areas:
            first = stats.top_areas[0]
            answer += f" {first.label} ghi nhận {first.count} báo cáo."
    note = " Kết quả giới hạn trong phần dữ liệu đã xử lý." if result.truncated else ""
    return ChatResult(
        reply=f"{prefix}, {answer}{note}",
        action="hotspots_admin" if scope == "admin" else "hotspots",
    )
