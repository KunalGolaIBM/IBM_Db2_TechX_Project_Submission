"""Structured logging. JSON lines in production (SHIPSAFE_LOG_FORMAT=json), readable text otherwise."""

import json
import logging
import re
import sys
import time

_SECRET = re.compile(r"(?i)(pwd=|password=|authorization: bearer |ss_)[^\s;\"']+")


class _Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET.sub(r"\1***", record.msg)
        if record.args:
            record.args = tuple(_SECRET.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_ms", "actor"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(fmt: str = "text", level: str = "INFO") -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(_Redact())
    handler.setFormatter(JsonFormatter() if fmt == "json"
                         else logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("uvicorn.access", "httpx", "langchain_db2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
