from fastapi import Query
from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    """Shared pagination query parameters (?page=1&page_size=25)."""

    def __init__(
        self,
        page: int = Query(1, ge=1, le=1_000_000),
        page_size: int = Query(25, ge=1, le=100),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
