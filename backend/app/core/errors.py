import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()

# Messages PostgreSQL/asyncpg produce for input the database can never store. These are client
# errors, not server faults, so they must not surface as a 500.
_DATA_ERRORS = (
    "invalid byte sequence",
    "out of int64 range",
    "out of range",
    "unsupported unicode escape",
    "cannot be converted to text",
    "value too long",
    "invalid input syntax",
)


class AppError(Exception):
    """Domain error with a stable machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _body(code: str, message: str, details=None) -> dict:
    err: dict = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"error": err}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DBAPIError)
    async def _db_error(_: Request, exc: DBAPIError):
        text = str(exc.orig).lower()
        if any(marker in text for marker in _DATA_ERRORS):
            return JSONResponse(
                _body("invalid_input", "The request contains a value that cannot be stored"),
                status_code=422,
            )
        log.exception("database_error")
        return JSONResponse(_body("internal_error", "Something went wrong"), status_code=500)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled_error", error=type(exc).__name__)
        return JSONResponse(_body("internal_error", "Something went wrong"), status_code=500)

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            _body("http_error", str(exc.detail)),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(_body("validation_error", "Invalid request", details), status_code=422)
