"""Treat all ingested content as untrusted data.

Evidence may contain prompt-injection text, HTML, shell metacharacters, or
malicious branch/path names. Evidence may influence editorial synthesis. It
must never gain execution authority, path-mutation authority, or the ability
to rewrite maintainer instructions.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_INSTRUCTION_PATTERNS = (
    re.compile(r"ignore (all|any|previous|prior) instructions", re.I),
    re.compile(r"(ignore|disregard)\b.{0,60}\b(instructions|rules)", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"disregard (the|these|previous) (rules|instructions)", re.I),
    re.compile(r"<(script|iframe|object|embed|link)\b", re.I),
)

# Patterns that must never appear in published journal prose. They either
# echo untrusted instructions back as text or assert authority the journal
# does not have.
_NORMATIVE_PATTERNS = (
    re.compile(r"ignore (all|any|previous|prior) (instructions|rules)", re.I),
    re.compile(r"disregard (the|these|previous|all) (rules|instructions|guidance)", re.I),
    re.compile(r"(this entry|this journal|this record) (now )?(overrides|supersedes|repeals)", re.I),
    re.compile(r"(is|are|becomes?) (now )?(normative|mandatory|required by specification)", re.I),
    re.compile(r"(hereby|is hereby) (declared|established|ratified|accepted)", re.I),
    re.compile(r"conformance (is|has been) (proven|verified|confirmed|achieved)", re.I),
    re.compile(r"(passes?|meets?|satisfies) (all |the )?(mncs|mncds) (conformance|requirements|standard)", re.I),
    re.compile(r"(specification|standard) (now )?(states|requires|mandates)", re.I),
    re.compile(r"accepted as (normative|governing|authoritative)", re.I),
)
_SHELL_UNSAFE = re.compile(r"[`$\\;&|<>\n\r]")
_SLUG_SAFE = re.compile(r"[^a-z0-9-]+")
_HYPHEN_RUNS = re.compile(r"-{2,}")


def scrub_text(value: object, *, limit: int = 4000) -> str:
    text = "" if value is None else str(value)
    text = _CONTROL_CHARS.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = text.strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def evidence_as_data(value: object, *, limit: int = 2000) -> str:
    """Wrap evidence so synthesis treats it as quoted data, not instructions."""
    text = scrub_text(value, limit=limit)
    if not text:
        return ""
    for pattern in _INSTRUCTION_PATTERNS:
        if pattern.search(text):
            text = f"[untrusted evidence; instruction-like text neutralized] {text}"
            break
    return text


def contains_instruction_like_text(value: object) -> bool:
    """Detect instruction-like text that must not pass through into prose."""

    text = scrub_text(value, limit=20000)
    return any(pattern.search(text) for pattern in _INSTRUCTION_PATTERNS)


def find_normative_language(value: object) -> list[str]:
    """Return the normative/authority-escalation phrases found in text."""

    text = scrub_text(value, limit=40000)
    matches: list[str] = []
    for pattern in _NORMATIVE_PATTERNS:
        found = pattern.search(text)
        if found:
            matches.append(found.group(0))
    return matches


def escape_html(value: object) -> str:
    return html.escape(scrub_text(value, limit=20000), quote=True)


def slugify(value: object, *, fallback: str = "development-notes", limit: int = 72) -> str:
    text = scrub_text(value, limit=200).lower()
    text = text.replace("_", "-").replace(" ", "-")
    text = _SLUG_SAFE.sub("-", text)
    text = _HYPHEN_RUNS.sub("-", text).strip("-")
    if not text:
        text = fallback
    return text[:limit].strip("-") or fallback


def safe_branch_name(value: object) -> str:
    text = slugify(value, fallback="journal-maintainer", limit=80)
    if not text.startswith("journal/"):
        text = f"journal/maintainer/{text}"
    if _SHELL_UNSAFE.search(text):
        raise ValueError("refusing unsafe branch name")
    return text


def safe_url(value: object) -> str | None:
    text = scrub_text(value, limit=500)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return text


def is_noise_title(title: str) -> bool:
    lowered = title.lower()
    noise_markers = (
        "dependabot",
        "bump ",
        "chore(deps)",
        "chore: deps",
        "update lockfile",
        "npm audit",
        "format",
        "prettier",
        "rustfmt",
        "gofmt",
        "whitespace",
        "typo",
        "spelling",
        "sync pages root",
        "resync",
    )
    if any(marker in lowered for marker in noise_markers):
        return True
    if re.fullmatch(r"(chore|ci|style|docs):\s*(typo|lint|format).*", lowered):
        return True
    return False
