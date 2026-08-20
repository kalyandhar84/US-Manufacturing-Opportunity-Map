"""Persist Contact us form submissions as local text files."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIL_DIR = ROOT / "mail"

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def sanitize_filename_part(name: str) -> str:
    slug = _UNSAFE.sub("_", (name or "").strip())[:40].strip("._")
    if not slug or slug in {".", ".."}:
        return "contact"
    return slug


def validate_contact(name: str, email: str, message: str) -> str | None:
    if not name.strip():
        return "Enter your name."
    if not _EMAIL.match(email.strip()):
        return "Enter a valid email address."
    if not message.strip():
        return "Enter a message."
    return None


def save_contact_message(*, name: str, email: str, company: str, message: str) -> Path:
    error = validate_contact(name, email, message)
    if error:
        raise ValueError(error)

    MAIL_DIR.mkdir(parents=True, exist_ok=True)
    mail_root = MAIL_DIR.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{stamp}_{sanitize_filename_part(name)}.txt"
    path = (mail_root / filename).resolve()
    if path.parent != mail_root:
        raise ValueError("Invalid submission path.")

    company_line = company.strip() or "(not provided)"
    body = (
        f"Submitted (UTC): {stamp}\n"
        f"Name: {name.strip()}\n"
        f"Email: {email.strip()}\n"
        f"Company: {company_line}\n"
        f"\n"
        f"Message:\n{message.strip()}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path
