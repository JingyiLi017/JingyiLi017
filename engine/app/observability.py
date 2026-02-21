from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "novel-engine",
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or get_request_id(),
            "job_id": getattr(record, "job_id", None),
            "job_type": getattr(record, "job_type", None),
            "stage": getattr(record, "stage", None),
        }
        meta = getattr(record, "meta", None)
        if isinstance(meta, dict):
            payload["meta"] = meta
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_novel_engine_configured", False):
        return
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root._novel_engine_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(request_id: str | None) -> contextvars.Token[str | None]:
    return _request_id_var.set(request_id)


def get_request_id() -> str | None:
    return _request_id_var.get()


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id_var.reset(token)

