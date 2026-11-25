import re
import unicodedata
from typing import Literal

RefusalReason = Literal["private_data", "security", "outside_scope"]

REFUSALS: dict[RefusalReason, str] = {
    "private_data": (
        "Mình không thể cung cấp thông tin đăng nhập, thông tin liên hệ riêng tư hoặc "
        "bằng chứng của người khác. Nếu bạn nhận ra món đồ, hãy mở tin và chọn "
        "“Đây là đồ của tôi” để gửi yêu cầu xác minh."
    ),
    "security": (
        "Mình chỉ có thể hỗ trợ trong phạm vi FindBack và theo quyền của tài khoản hiện tại. "
        "Bạn có thể hỏi về tin công khai, tin của mình hoặc quy trình nhận đồ."
    ),
    "outside_scope": (
        "Mình hỗ trợ các câu hỏi về FindBack, tin mất và nhặt đồ, địa điểm trong tin "
        "và quy trình nhận lại đồ. Bạn muốn mình giúp phần nào?"
    ),
}

SECRET = re.compile(
    r"(?i)\b(?:bearer\s+[^\s,;]+|sk-[\w-]{12,}|eyJ[\w-]+\.[\w-]+\.[\w-]+"
    r"|(?:mật khẩu|mat khau|password|api[_ -]?key|otp)\s*[:=]\s*[^\s,;]+)"
)
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE = re.compile(r"(?<!\w)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)")
ACCOUNT_HELP = re.compile(
    r"(?:(?:toi|minh|em) (?:bi )?)?quen mat khau(?: (?:findback|cua toi))?"
    r"(?: (?:thi )?(?:lam sao|lam the nao)(?: de dang nhap)?)?"
    r"|(?:cach|lam sao(?: de)?|lam the nao(?: de)?) "
    r"(?:doi|dat lai|khoi phuc) mat khau(?: (?:findback|cua toi))?"
)
CREDENTIALS = re.compile(
    r"\b(?:mat khau|password|passcode|credentials|ma otp|otp|api key|khoa api|"
    r"access token|refresh token|jwt|ma pin|ma dang nhap|login credentials)\b"
)
PRIVATE_RECORDS = re.compile(
    r"\b(?:so dien thoai|sdt|so cccd|so can cuoc|so ho chieu|dia chi nha|"
    r"phone number|home address|private data|noi dung bang chung|bang chung rieng tu|"
    r"thong tin ca nhan|du lieu rieng tu)\b"
)
SUBJECT = (
    r"(?:nguoi dang|chu tin|chu bai|chu do|nguoi khac|nguoi nhat|nguoi mat|"
    r"poster|other user|their|someone)"
)
PRIVATE_CONTACT = re.compile(
    rf"\b(?:tai khoan|email|thong tin lien he|bang chung|account|contact details)"
    rf"\b.{{0,48}}\b{SUBJECT}\b|\b{SUBJECT}\b.{{0,48}}"
    r"\b(?:email|tai khoan|account|contact details)\b"
)
DISCLOSURE_REQUEST = re.compile(
    r"\b(?:cho (?:toi|minh|em) (?:xin |xem |biet )?|gui cho (?:toi|minh|em) |"
    r"cung cap (?:cho (?:toi|minh|em) )?|tra cuu |tim (?:cho|ho|giup) (?:toi|minh|em) |"
    r"lay (?:cho|ho|giup) (?:toi|minh|em) |give me |show me )"
    r"(?:tai khoan|mat khau|password|email|so dien thoai|sdt|so cccd|so can cuoc|"
    r"so ho chieu|dia chi nha|ma otp|otp|ma pin|api key|khoa api|access token|"
    r"refresh token|jwt|ma dang nhap|thong tin lien he|thong tin ca nhan|"
    r"du lieu rieng tu|noi dung bang chung|bang chung rieng tu|"
    r"phone number|home address|credentials|private data)\b"
)
THIRD_PARTY = re.compile(rf"\b{SUBJECT}\b")
ASKS_FOR_VALUE = re.compile(r"\b(?:la gi|la bao nhieu|so bao nhieu|cho biet|muon biet|what is)\b")
SECURITY = re.compile(
    r"\b(?:system prompt|developer message|system instructions|lenh he thong|"
    r"prompt he thong|chi dan noi bo|chi dan he thong|vuot quyen|bo qua bao mat|"
    r"hay (?:gia danh|mao danh|dong gia)|bypass|"
    r"ignore (?:all |the )?(?:previous|prior) instructions|"
    r"bo qua (?:tat ca )?(?:cac )?(?:quy tac|chi dan|huong dan)|"
    r"(?:truy cap|xuat|doc|dump|export) (?:co so du lieu|database))\b"
)


def without_format_characters(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKC", text) if unicodedata.category(char) != "Cf"
    )


def redact_sensitive_text(text: str) -> str:
    clean = SECRET.sub("[đã ẩn]", without_format_characters(text))
    return PHONE.sub("[đã ẩn]", EMAIL.sub("[đã ẩn]", clean))


def normalized_question(text: str) -> str:
    text = unicodedata.normalize("NFKD", without_format_characters(text)).casefold()
    folded = "".join(char for char in text if not unicodedata.combining(char)).replace("đ", "d")
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def local_refusal(message: str) -> RefusalReason | None:
    question = normalized_question(message)
    if SECURITY.search(question):
        return "security"
    if ACCOUNT_HELP.fullmatch(question):
        return None
    sensitive = CREDENTIALS.search(question) or PRIVATE_RECORDS.search(question)
    if DISCLOSURE_REQUEST.search(question) or (
        (PRIVATE_CONTACT.search(question) or (sensitive and THIRD_PARTY.search(question)))
        and ASKS_FOR_VALUE.search(question)
    ):
        return "private_data"
    return None
