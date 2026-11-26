from typing import Literal

LocationCode = Literal["VN-HN", "VN-SG", "VN-DN", "OTHER"]
HotspotZone = Literal[
    "LIBRARY", "CAFETERIA", "PARKING", "CLASSROOM", "SPORTS", "DORMITORY", "OTHER"
]

LOCATIONS = {
    "VN-HN": "Hà Nội",
    "VN-SG": "TP. Hồ Chí Minh",
    "VN-DN": "Đà Nẵng",
    "OTHER": "Khu vực khác",
}

HOTSPOT_ZONES = {
    "LIBRARY": "Thư viện",
    "CAFETERIA": "Căn tin",
    "PARKING": "Bãi gửi xe",
    "CLASSROOM": "Khu giảng đường",
    "SPORTS": "Khu thể thao",
    "DORMITORY": "Ký túc xá",
    "OTHER": "Địa điểm công cộng khác",
}
