"""Host-boundary rendering: validated payload -> static site artifacts.

Writes ``site/dashboard.json`` (the full envelope) and refreshes the
``<noscript>`` fallback table inside ``site/dashboard.html`` so core facts
remain readable when WASM or JavaScript is unavailable.  The envelope
carries only deterministic provenance (never wall-clock time), so
re-rendering unchanged state produces byte-identical output.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from registry.model import canonical_bytes

from . import PROJECTOR_ID, PROJECTOR_VERSION
from .project import semantic_hash

DASHBOARD_JSON = Path("site/dashboard.json")
DASHBOARD_HTML = Path("site/dashboard.html")
NOSCRIPT_BEGIN = "<!-- MNCS:generated:begin -->"
NOSCRIPT_END = "<!-- MNCS:generated:end -->"


def envelope(payload: dict[str, Any], *, source_epoch: str | None = None,
             observed: dict[str, str] | None = None) -> dict[str, Any]:
    """Wrap a validated payload with projector identity (outside the hash).

    The envelope is fully deterministic: provenance travels as the
    observed semantic epoch (supplied by ambient callers) rather than a
    wall-clock timestamp, so re-rendering unchanged state is byte-identical.
    """
    block: dict[str, Any] = {
        "projector": PROJECTOR_ID,
        "projector_version": PROJECTOR_VERSION,
    }
    if source_epoch is not None:
        block["source_epoch"] = source_epoch
    if observed is not None:
        block["observed_sources"] = observed
    return {
        "envelope": block,
        "semantic_hash": payload["semantic_hash"],
        "projection": payload,
    }


def envelope_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def read_previous(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def semantic_changed(previous: dict[str, Any] | None, fresh_hash: str) -> bool:
    """No-change detection: only the semantic hash decides, never timestamps."""
    if not isinstance(previous, dict):
        return True
    return previous.get("semantic_hash") != fresh_hash


def noscript_table(payload: dict[str, Any]) -> str:
    """Static fallback: ecosystem + provenance summary as plain HTML."""
    ecosystem = payload.get("ecosystem", {})
    projects = ecosystem.get("projects", []) if isinstance(ecosystem, dict) else []
    rows = []
    for entry in projects:
        if not isinstance(entry, dict):
            continue
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(entry.get("id", ""))),
                html.escape(str(entry.get("category", ""))),
                html.escape(str(entry.get("lifecycle", ""))),
                html.escape(str(entry.get("authority_class", ""))),
                html.escape(str(entry.get("maturity", ""))),
            )
        )
    freshness = payload.get("freshness", {})
    semantic = payload.get("semantic_hash", "")
    return (
        "<table>"
        "<caption>Atlas dashboard projection {sem} (freshness: {fresh}) — "
        "full data in dashboard.json</caption>"
        "<thead><tr><th>project</th><th>category</th><th>lifecycle</th>"
        "<th>authority</th><th>maturity</th></tr></thead>"
        "<tbody>{rows}</tbody></table>"
    ).format(
        sem=html.escape(str(semantic)),
        fresh=html.escape(str(freshness.get("status", "unknown")) if isinstance(freshness, dict) else "unknown"),
        rows="".join(rows),
    )


def refresh_noscript(html_path: Path, payload: dict[str, Any]) -> bool:
    """Replace the noscript fallback block; return True when the file changed."""
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return False
    begin = text.find(NOSCRIPT_BEGIN)
    end = text.find(NOSCRIPT_END)
    if begin < 0 or end < begin:
        return False
    replacement = (
        text[: begin + len(NOSCRIPT_BEGIN)]
        + "\n<noscript>\n"
        + noscript_table(payload)
        + "\n</noscript>\n"
        + text[end:]
    )
    if replacement == text:
        return False
    html_path.write_text(replacement, encoding="utf-8")
    return True


def verify_semantic_hash(payload: dict[str, Any]) -> bool:
    """Recompute the hash over the payload minus itself; must match."""
    candidate = {key: value for key, value in payload.items() if key != "semantic_hash"}
    return semantic_hash(candidate) == payload.get("semantic_hash")


def verify_envelope(data: dict[str, Any]) -> bool:
    projection = data.get("projection")
    if not isinstance(projection, dict):
        return False
    if data.get("semantic_hash") != projection.get("semantic_hash"):
        return False
    return verify_semantic_hash(projection) and canonical_bytes(projection) is not None
