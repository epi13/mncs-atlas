"""Orientation projections: one state, two presentations.

:func:`machine_orientation` answers, as data, what an arriving agent needs:
where it is, what exists, its goal, what it may read/do, what it may not do
and why, which conformant path exists, what evidence is required, and who
owns each decision. :func:`human_orientation` renders the same state as
readable prose. Both derive from the same session, router decisions, and
Atlas map, so the two views cannot drift apart.
"""

from __future__ import annotations

import json
from pathlib import Path

from .model import Session
from .router import Router
from .vocabulary import SENSITIVITY_LADDER, capability_ids, describe_capability

ADMISSION_SCHEMA_VERSION = "mncs.atlas-orientation/1"


def find_repo_root(start: Path) -> Path:
    """Locate the mncs-atlas checkout root from any path inside it."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "site" / "atlas.json").is_file():
            return candidate
    raise FileNotFoundError("mncs-atlas checkout root not found")


def load_atlas_map(root: Path | None = None) -> dict:
    """Load the canonical machine-readable family map (orientation data)."""
    base = root or find_repo_root(Path(__file__))
    with open(base / "site" / "atlas.json", encoding="utf-8") as handle:
        return json.load(handle)


def load_admission_map(root: Path | None = None, atlas_map: dict | None = None) -> dict:
    """Load the generated admission/capability map via the atlas pointer.

    Discovery is two documents: ``atlas.json`` names the admission document
    and pins its version; ``admission.json`` carries the capability catalog.
    """
    base = root or find_repo_root(Path(__file__))
    atlas_map = atlas_map if atlas_map is not None else load_atlas_map(base)
    pointer = atlas_map.get("admission", {})
    document = pointer.get("document", "admission.json")
    path = base / "site" / document
    with open(path, encoding="utf-8") as handle:
        admission_map = json.load(handle)
    if admission_map.get("version") != pointer.get("version"):
        raise ValueError("admission document drifts from the atlas admission pointer")
    return admission_map


def _capability_statuses(
    session: Session,
    router: Router,
    scope: str = "",
    context: dict | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    context = context or {}
    granted: list[dict] = []
    conditional: list[dict] = []
    denied: list[dict] = []
    for capability_id in capability_ids():
        decision = router.query(session, capability_id, scope=scope, **context)
        entry = {
            "capability": capability_id,
            "authority": decision["authority"],
            "scope": decision["scope"],
            "reason": decision["reason"],
            "missing": decision["missing"],
            "evidence_required": decision["evidence_required"],
            "conformant_path": decision["conformant_path"],
        }
        if decision["status"] == "granted":
            granted.append(entry)
        elif decision["status"] == "conditional":
            conditional.append(entry)
        else:
            denied.append(entry)
    return granted, conditional, denied


def machine_orientation(
    session: Session,
    router: Router | None = None,
    atlas_map: dict | None = None,
    scope: str = "",
    context: dict | None = None,
    admission_map: dict | None = None,
) -> dict:
    """Machine-readable orientation for an arriving participant."""
    router = router or Router()
    atlas_map = atlas_map if atlas_map is not None else load_atlas_map()
    if admission_map is None:
        admission_map = load_admission_map(atlas_map=atlas_map)
    granted, conditional, denied = _capability_statuses(session, router, scope, context)
    projects = atlas_map.get("projects", [])
    return {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "authority": "orientation-only",
        "admission": {
            "document": (atlas_map.get("admission", {}) or {}).get("document", "admission.json"),
            "version": admission_map.get("version"),
            "states": admission_map.get("states", []),
            "capability_count": len(admission_map.get("capabilities", [])),
        },
        "where_am_i": {
            "ecosystem": "MNCS project family",
            "atlas_version": session.atlas_version,
            "repository_context": session.repository_context or "unspecified",
            "admission_state": session.state,
        },
        "what_exists": {
            "components": [
                {
                    "id": item.get("id"),
                    "role": item.get("role"),
                    "authority_class": item.get("authority_class"),
                    "maturity": item.get("maturity"),
                }
                for item in projects
                if isinstance(item, dict)
            ],
            "entry_points": atlas_map.get("entry_points", []),
        },
        "what_is_my_goal": session.purpose or "unspecified",
        "what_can_i_read": [item for item in granted
                            if describe_capability(item["capability"])["sensitivity"]
                            in ("open", "scoped")],
        "what_can_i_do": granted,
        "what_can_i_not_do": denied,
        "conditional_capabilities": conditional,
        "why_is_it_denied": {
            item["capability"]: {
                "reason": item["reason"],
                "authority": item["authority"],
            }
            for item in denied
        },
        "what_conformant_path_exists": {
            item["capability"]: item["conformant_path"]
            for item in denied + conditional
            if item["conformant_path"]
        },
        "what_evidence_is_required": {
            item["capability"]: item["evidence_required"]
            for item in denied + conditional
            if item["evidence_required"]
        },
        "who_has_authority": {
            capability_id: describe_capability(capability_id)["owner"]
            for capability_id in capability_ids()
        },
        "participant": session.participant.to_dict(),
        "sensitivity_ladder": list(SENSITIVITY_LADDER),
    }


def human_orientation(
    session: Session,
    router: Router | None = None,
    atlas_map: dict | None = None,
    scope: str = "",
    context: dict | None = None,
    admission_map: dict | None = None,
) -> str:
    """Human-readable orientation rendered from the same state as the machine view."""
    state = machine_orientation(session, router, atlas_map, scope, context, admission_map)
    lines = [
        "# MNCS orientation",
        "",
        "Atlas grants entry, not trust. This view and the machine-readable "
        "orientation derive from the same session state.",
        "",
        f"You are a {session.participant.type} participant "
        f"({session.participant.identity}) in admission state {session.state}.",
    ]
    where = state["where_am_i"]
    lines.append(
        f"Context: {where['repository_context']} (Atlas {where['atlas_version']})."
    )
    if session.purpose:
        lines.append(f"Stated goal: {session.purpose}")
    lines += ["", "## What you may do"]
    if state["what_can_i_do"]:
        for item in state["what_can_i_do"]:
            lines.append(f"- {item['capability']} (scope: {item['scope'] or 'ecosystem'})")
    else:
        lines.append("- Nothing yet: complete admission first.")
    if state["conditional_capabilities"]:
        lines += ["", "## Conditional: missing evidence"]
        for item in state["conditional_capabilities"]:
            missing = ", ".join(item["missing"]) or "evidence review"
            lines.append(f"- {item['capability']}: missing {missing}.")
    if state["what_can_i_not_do"]:
        lines += ["", "## Denied and why"]
        for item in state["what_can_i_not_do"]:
            lines.append(
                f"- {item['capability']}: {item['reason']} "
                f"[authority: {item['authority']}]"
            )
            if item["conformant_path"]:
                lines.append(f"  Conformant path: {' -> '.join(item['conformant_path'])}")
    lines += [
        "",
        "Authority for each capability sits with the owning subsystem, "
        "never with Atlas. Understanding this map grants no authority.",
    ]
    return "\n".join(lines) + "\n"
