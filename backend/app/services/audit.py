import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

_SENSITIVE = {"password", "token", "refresh_token", "access_token", "secret"}


def _clean(value):
    """PostgreSQL JSONB cannot hold NUL characters."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _redact(data: dict | None) -> dict | None:
    if not data:
        return data
    data = _clean(data)
    return {k: ("[redacted]" if k.lower() in _SENSITIVE else v) for k, v in data.items()}


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    outcome: str,
    actor_user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Adds an audit row to the caller's transaction (caller commits)."""
    db.add(
        AuditLog(
            action=action,
            outcome=outcome,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            metadata_=_redact(metadata),
            ip_address=ip_address,
        )
    )
