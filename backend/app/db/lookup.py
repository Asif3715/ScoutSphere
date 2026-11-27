"""Loading rows that the data model guarantees exist (a foreign key points at them)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def get_required[T](db: AsyncSession, model: type[T], ident: Any) -> T:
    """`db.get` for a row that must be there. Its absence is a bug, not a user error."""
    obj = await db.get(model, ident)
    if obj is None:
        raise LookupError(f"{model.__name__} {ident} is missing")
    return obj
