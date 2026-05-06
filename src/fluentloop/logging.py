from __future__ import annotations

import logging
import re

TOKEN_RE = re.compile(
    r"(\b\d{6,}:[A-Za-z0-9_-]{20,}\b|sk-[A-Za-z0-9_-]{20,}|xoxb-[A-Za-z0-9-]+)"
)


class MaskingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return TOKEN_RE.sub("<secret>", message)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        MaskingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
