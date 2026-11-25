import re

# Vietnamese title aliases and English prompts for the existing OpenCLIP model.
ITEM_TYPES = {
    "laptop": (
        "Laptop",
        ("laptop", "máy tính xách tay", "macbook", "vivobook"),
        "an open laptop computer with a keyboard and screen",
    ),
    "phone": (
        "Điện thoại",
        ("điện thoại", "smartphone", "iphone"),
        "a mobile smartphone, with or without a protective folio case",
    ),
    "camera": (
        "Máy ảnh",
        ("máy ảnh", "camera", "máy chụp ảnh"),
        "a stand-alone digital photo camera with a lens",
    ),
    "wallet": (
        "Ví",
        ("ví", "bóp", "ví tiền"),
        "a small folding leather wallet for cards and money",
    ),
    "backpack": (
        "Ba lô",
        ("ba lô", "balo", "ba-lô", "backpack"),
        "a fabric backpack with shoulder straps",
    ),
    "bag": ("Túi xách", ("túi xách", "túi đeo", "túi tote"), "a handbag or shoulder tote bag"),
    "keys": (
        "Chìa khóa",
        ("chìa khóa", "chìa khoá", "chìa xe", "keyring"),
        "a small set of metal keys on a keyring",
    ),
    "glasses": (
        "Kính",
        ("kính cận", "kính mắt", "kính", "gọng kính"),
        "a pair of optical eyeglasses with two lenses and a frame",
    ),
    "watch": (
        "Đồng hồ",
        ("đồng hồ", "smartwatch"),
        "a wristwatch with a round watch face and a wrist strap",
    ),
    "bottle": (
        "Bình nước",
        ("bình nước", "bình giữ nhiệt", "chai nước"),
        "a reusable water bottle or thermos with a screw top",
    ),
    "headphones": (
        "Tai nghe",
        ("tai nghe", "airpods", "earbuds"),
        "audio headphones or wireless earbuds",
    ),
    "umbrella": (
        "Ô hoặc dù",
        ("ô gấp", "ô màu", "ô đen", "cây dù", "dù che mưa"),
        "a handheld rain umbrella",
    ),
    "book": (
        "Sách hoặc sổ",
        ("cuốn sách", "quyển sách", "sách", "sổ tay"),
        "a book or paper notebook with pages",
    ),
    "pencil_case": ("Túi bút", ("túi bút", "hộp bút"), "a zippered pencil case for pens"),
    "card": (
        "Thẻ hoặc giấy tờ",
        ("thẻ", "giấy tờ", "căn cước", "hộ chiếu"),
        "a loose plastic card or identification document by itself",
    ),
}
PROMPTS = {key: kind[2] for key, kind in ITEM_TYPES.items()}
PROMPTS["background"] = "an outdoor landscape or a scene without a single small object"
TITLE_PATTERNS = {
    key: re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, aliases)) + r")(?!\w)", re.I)
    for key, (_, aliases, _) in ITEM_TYPES.items()
}


def title_item_type(title: str | None) -> str | None:
    matches = [key for key, pattern in TITLE_PATTERNS.items() if pattern.search(title or "")]
    return matches[0] if len(matches) == 1 else None
