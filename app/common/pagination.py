from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool


def paginate_params(limit: int = 20, offset: int = 0) -> tuple[int, int]:
    """Clamp pagination params to sane bounds."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return limit, offset
