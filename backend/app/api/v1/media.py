"""Delivery of uploaded media through signed URLs (see services/media.py)."""

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

from app.services import media

router = APIRouter(prefix="/media", tags=["media"])

_NOT_FOUND = {"error": {"code": "not_found", "message": "Not found"}}


@router.get("/{key:path}", include_in_schema=False)
async def get_media(key: str, exp: int = Query(...), sig: str = Query(..., max_length=64)):
    # One answer for every failure (bad signature, expired, missing): reveal nothing.
    path = media.storage().path(key) if media.verify(key, exp, sig) else None
    if path is None:
        return JSONResponse(_NOT_FOUND, status_code=404)
    max_age = media.get_settings().media_url_hours * 3600
    return FileResponse(
        path,
        media_type="image/webp",
        headers={
            # private: per-user signed URL; safe to keep until the signature expires
            "Cache-Control": f"private, max-age={max_age}, immutable",
            "Content-Disposition": "inline",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )
