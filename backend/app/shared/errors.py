from fastapi import HTTPException, status


class AppError(HTTPException):
    """Base application exception."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(AppError):
    def __init__(self, detail: str = "Tài nguyên không tìm thấy"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Bạn không có quyền thực hiện thao tác này"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Chưa xác thực hoặc token không hợp lệ"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ConflictError(AppError):
    def __init__(self, detail: str = "Xung đột trạng thái dữ liệu"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class BadRequestError(AppError):
    def __init__(self, detail: str = "Yêu cầu không hợp lệ"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ValidationError(AppError):
    def __init__(self, detail: str = "Dữ liệu không hợp lệ"):
        super().__init__(status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422), detail=detail)
