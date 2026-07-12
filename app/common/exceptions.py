from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base class for our own app-specific errors, so routers can raise
    something more descriptive than a bare HTTPException."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail)


class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail)


class ForbiddenError(AppException):
    def __init__(self, detail: str = "You don't have access to this resource"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail)


class ConflictError(AppException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail)
