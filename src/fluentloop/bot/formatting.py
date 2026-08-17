from __future__ import annotations

from html import escape

HTML_PARSE_MODE = "html"


def html_escape(value: object) -> str:
    return escape(str(value), quote=False)


def bold(value: object) -> str:
    return f"<b>{html_escape(value)}</b>"


def italic(value: object) -> str:
    return f"<i>{html_escape(value)}</i>"


def code(value: object) -> str:
    return f"<code>{html_escape(value)}</code>"


def labeled(label: str, value: object) -> str:
    return f"{bold(label + ':')} {html_escape(value)}"


def quote_line(value: object) -> str:
    return code(value)
