"""Schema validation and public-data sanitization for the projection.

Validation is hand-rolled and dependency-free (like ``scripts/check_site.py``)
so the controller never needs more than the standard library.  Sanitization
is an allowlist: only scalar fields named here may reach the public
artifact, which keeps machine-local paths, credentials, and conversation
data out of Pages output by construction.
"""

from __future__ import annotations

from typing import Any

from . import PROJECTION_SCHEMA

TOP_LEVEL = (
    "schema_version",
    "semantic_hash",
    "sources",
    "freshness",
    "ecosystem",
    "relationships",
    "capabilities",
    "implementation",
    "pressures",
    "verification",
    "movement",
    "journal",
)

SOURCE_FIELDS = ("id", "path", "content_sha256", "status", "reason")
SOURCE_STATUSES = ("present", "missing", "invalid")

PROJECT_FIELDS = (
    "id",
    "name",
    "category",
    "purpose",
    "role",
    "lifecycle",
    "lifecycle_reason",
    "authority_class",
    "authority_reason",
    "maturity",
    "maturity_reason",
    "repository",
    "dependencies",
    "observed_in_workspace",
    "manifest",
    "participation",
)


def _errors_for_source(source: Any, index: int) -> list[str]:
    errors: list[str] = []
    label = f"sources[{index}]"
    if not isinstance(source, dict):
        return [f"{label} must be an object"]
    for field in SOURCE_FIELDS:
        if field not in source:
            errors.append(f"{label} is missing {field}")
    if source.get("status") not in SOURCE_STATUSES:
        errors.append(f"{label}.status is invalid: {source.get('status')!r}")
    digest = source.get("content_sha256")
    if source.get("status") == "present" and not isinstance(digest, str):
        errors.append(f"{label} present without a content identity")
    return errors


def validate(payload: Any) -> list[str]:
    """Return a list of schema violations (empty means valid)."""
    if not isinstance(payload, dict):
        return ["projection must be a JSON object"]
    errors: list[str] = []
    for field in TOP_LEVEL:
        if field not in payload:
            errors.append(f"projection is missing {field}")
    if payload.get("schema_version") != PROJECTION_SCHEMA:
        errors.append(f"schema_version must be {PROJECTION_SCHEMA}")
    semantic = payload.get("semantic_hash")
    if not isinstance(semantic, str) or not semantic.startswith("sha256:"):
        errors.append("semantic_hash must be a sha256: identity")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
    else:
        for index, source in enumerate(sources):
            errors.extend(_errors_for_source(source, index))
    ecosystem = payload.get("ecosystem")
    if not isinstance(ecosystem, dict) or not isinstance(ecosystem.get("projects"), list):
        errors.append("ecosystem.projects must be a list")
    else:
        ids = [
            entry.get("id")
            for entry in ecosystem["projects"]
            if isinstance(entry, dict)
        ]
        if len(set(ids)) != len(ids):
            errors.append("ecosystem.projects contains duplicate ids")
        if ids != sorted(ids):
            errors.append("ecosystem.projects must be sorted by id")
        for entry in ecosystem["projects"]:
            if not isinstance(entry, dict):
                errors.append("ecosystem.projects entries must be objects")
                break
            for field in PROJECT_FIELDS:
                if field not in entry:
                    errors.append(f"project {entry.get('id')!r} is missing {field}")
                    break
    pressures = payload.get("pressures")
    if isinstance(pressures, dict) and isinstance(pressures.get("listed"), list):
        listed = pressures["listed"]
        keys = [str(item.get("id")) for item in listed if isinstance(item, dict)]
        if keys != sorted(keys):
            errors.append("pressures.listed must be sorted by id")
    return errors


def sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    """Project the payload through the public-field allowlist.

    Unknown top-level sections and unknown project fields are dropped rather
    than published.  Anything that is not a JSON scalar, list, or dict of
    those is rejected loudly instead of being coerced.
    """
    clean: dict[str, Any] = {}
    for field in TOP_LEVEL:
        clean[field] = _sanitize_value(payload.get(field), field)
    return clean


def _sanitize_value(value: Any, label: str) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_sanitize_value(item, label) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item, f"{label}.{key}") for key, item in value.items()}
    raise ValueError(f"unsanitizable value at {label}: {type(value).__name__}")
