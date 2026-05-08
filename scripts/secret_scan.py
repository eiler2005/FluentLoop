#!/usr/bin/env python3
"""Repository-specific secret scanner for public-git hygiene.

The scanner is intentionally small and conservative. It checks tracked and
untracked non-ignored text files for FluentLoop's common leak modes: Telegram
tokens and numeric IDs, AI keys, private key markers, public VPS IPs, and
secret-looking env assignments.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".venv/",
    "build/",
    "data/",
    "dist/",
    "feedback_disputes/",
    "logs/",
    "reports/",
    "secrets/",
    "state/",
)

BINARY_SUFFIXES = (
    ".db",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".pyc",
    ".session",
    ".sqlite",
    ".sqlite3",
    ".webp",
)

ALLOW_PUBLIC_IPS = {
    "1.1.1.1",
    "1.0.0.1",
    "8.8.8.8",
    "8.8.4.4",
    "9.9.9.9",
    "149.112.112.112",
}

ALLOW_PUBLIC_IP_FILES: set[str] = set()

SECRET_ENV_NAMES = {
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "TELEGRAM_API_HASH",
    "TELEGRAM_API_ID",
    "TELEGRAM_ALLOWED_USER_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TELEGRAM_FORUM_GROUP_ID",
    "VPS_HOST",
    "VPS_PORT",
    "VPS_USER",
}

SAFE_ENV_VALUES = {
    "",
    "0",
    "22",
    "false",
    "null",
    "STUB_OVERNIGHT_BUILD",
    "true",
}

PLACEHOLDER_MARKERS = (
    "<",
    ">",
    "example",
    "placeholder",
    "FILL_ME",
    "your-",
)

KNOWN_SENSITIVE_LITERALS = {
    ".".join(("204", "168", "239", "217")): "real FluentLoop VPS IPv4",
    "".join(("220", "587", "840")): "real Telegram allowed user id",
}

BOT_TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
ANTHROPIC_KEY_RE = re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")
PRIVATE_KEY_RE = re.compile(r"BEGIN (?:OPENSSH|RSA|EC|DSA|PRIVATE) KEY")
IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ENV_ASSIGN_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*['\"]?([^'\"\s#]+)?")
GENERIC_SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(password|passwd|token|api[_-]?key|private[_-]?key|secret)\s*[:=]\s*['\"]?([^'\"\s#]+)"
)


def git_output(*args: str) -> list[str]:
    output = subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    return [line for line in output.splitlines() if line]


def git_text(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def candidate_files() -> list[Path]:
    tracked = git_output("ls-files")
    untracked = git_output("ls-files", "--others", "--exclude-standard")
    paths = sorted(set(tracked + untracked))
    result: list[Path] = []
    for rel in paths:
        if rel.startswith(SKIP_PREFIXES):
            continue
        path = ROOT / rel
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        if path.is_file():
            result.append(path)
    return result


def is_placeholder(value: str) -> bool:
    if value in SAFE_ENV_VALUES:
        return True
    if any(marker in value for marker in PLACEHOLDER_MARKERS):
        return True
    return value.startswith("${") or value.startswith("$")


def is_public_ip(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    )


def fake_context(line: str) -> bool:
    markers = ("FAKE", "example.invalid", "<", "{{", "placeholder")
    return any(marker in line for marker in markers)


def scan_file(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if PRIVATE_KEY_RE.search(line):
            findings.append(f"{rel}:{lineno}: private key marker")
        if BOT_TOKEN_RE.search(line):
            findings.append(f"{rel}:{lineno}: Telegram bot token-looking value")
        if OPENAI_KEY_RE.search(line) or ANTHROPIC_KEY_RE.search(line):
            findings.append(f"{rel}:{lineno}: AI API key-looking value")
        for literal, reason in KNOWN_SENSITIVE_LITERALS.items():
            if literal in line:
                findings.append(f"{rel}:{lineno}: {reason}")
        env_match = ENV_ASSIGN_RE.match(line)
        if env_match:
            key, value = env_match.group(1), env_match.group(2) or ""
            if key in SECRET_ENV_NAMES and not is_placeholder(value):
                findings.append(f"{rel}:{lineno}: real-looking {key} assignment")
        if path.suffix.lower() not in {".py"}:
            for generic in GENERIC_SECRET_ASSIGN_RE.finditer(line):
                value = generic.group(2) or ""
                if value and not is_placeholder(value) and not fake_context(line):
                    findings.append(f"{rel}:{lineno}: secret-looking assignment")
        if rel not in ALLOW_PUBLIC_IP_FILES:
            for ip in IPV4_RE.findall(line):
                if is_public_ip(ip) and ip not in ALLOW_PUBLIC_IPS:
                    findings.append(f"{rel}:{lineno}: public IPv4 outside allowlist")
        if EMAIL_RE.search(line) and not fake_context(line):
            findings.append(f"{rel}:{lineno}: email address")
    return findings


def scan_history() -> list[str]:
    findings: list[str] = []
    revisions = git_output("rev-list", "--all")
    if not revisions:
        return findings

    max_lines_per_literal = 20
    for literal, reason in KNOWN_SENSITIVE_LITERALS.items():
        try:
            output = git_text("grep", "-n", "-I", "-F", literal, *revisions, "--")
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 1:
                continue
            raise
        lines = output.splitlines()
        for line in lines[:max_lines_per_literal]:
            findings.append(f"history:{reason}: {line}")
        hidden = len(lines) - max_lines_per_literal
        if hidden > 0:
            findings.append(
                f"history:{reason}: {hidden} more matches omitted; "
                "sanitize history before public push"
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan FluentLoop for sensitive data.")
    parser.add_argument(
        "--history",
        action="store_true",
        help="also scan git history for known production literals",
    )
    args = parser.parse_args()

    findings: list[str] = []
    for path in candidate_files():
        findings.extend(scan_file(path))
    if args.history:
        findings.extend(scan_history())
    if findings:
        print("Potential sensitive data found:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print("secret-scan: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
