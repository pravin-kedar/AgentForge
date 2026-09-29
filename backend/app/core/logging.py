import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
conversation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("conversation_id", default="")

_REDACT_KEYS = {"password", "token", "access_token", "authorization", "api_key", "jwt_secret_key", "groq_api_key"}


def redact(data: dict[str, Any]) -> dict[str, Any]:
    """Shallow-redact known-sensitive keys before they reach the logs."""
    return {k: ("***" if k.lower() in _REDACT_KEYS else v) for k, v in data.items()}


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id_var.get():
            payload["request_id"] = request_id_var.get()
        if user_id_var.get():
            payload["user_id"] = user_id_var.get()
        if conversation_id_var.get():
            payload["conversation_id"] = conversation_id_var.get()
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(redact(extra))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"extra_fields": fields})


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_var.set(request_id)
    logger = logging.getLogger("agentforge.request")
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        log_event(
            logger, logging.ERROR, "request_failed",
            method=request.method, path=request.url.path, duration_ms=round(duration_ms, 2),
        )
        raise
    duration_ms = (time.perf_counter() - start) * 1000
    log_event(
        logger, logging.INFO, "request_completed",
        method=request.method, path=request.url.path,
        status_code=response.status_code, duration_ms=round(duration_ms, 2),
    )
    response.headers["X-Request-ID"] = request_id
    return response
