#!/usr/bin/env python3
"""Synchronize the generated Atlas admission documents.

The participant capability vocabulary is canonical in
:mod:`admission.vocabulary`. This script projects it into two discovery
documents:

- ``site/admission.json``: the full machine-readable capability map
  (states, capabilities, authority ownership, rights scopes, lifecycle
  gates). Written wholesale; the vocabulary is the only source.
- ``site/atlas.json`` member ``admission``: a small pointer
  (``document``/``version``/``authority``/``note``) so the family map stays
  within the fixed input envelope of the experimental compiled atlas-model
  projection. See docs/ADMISSION.md ("language pressure") for why the full
  map lives beside the core map instead of inside it.

``--check`` verifies the committed documents match the vocabulary without
writing (CI gate).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_ATLAS = ROOT / "site" / "atlas.json"
SITE_ADMISSION = ROOT / "site" / "admission.json"

sys.path.insert(0, str(ROOT))

from admission.vocabulary import (  # noqa: E402
    ADMISSION_STATES,
    CAPABILITIES,
    LIFECYCLE_GATE,
    RIGHTS_SCOPE_FOR_CAPABILITY,
    SENSITIVITY_LADDER,
    VOCABULARY_VERSION,
)


def build_admission_document() -> dict:
    return {
        "schema_version": "mncs.atlas-admission-map/1",
        "version": VOCABULARY_VERSION,
        "authority": "orientation-only",
        "note": (
            "Participant admission and capability orientation. Atlas grants "
            "entry, context, discovery, and access to capability requests; "
            "it does not grant trust and never overrides owning subsystems."
        ),
        "states": list(ADMISSION_STATES),
        "state_policy": (
            "OUTSIDE -> KNOWN -> ADMITTED -> SCOPED, then per-capability "
            "CONFORMANT_FOR_CAPABILITY. No universal trusted flag exists."
        ),
        "sensitivity_ladder": list(SENSITIVITY_LADDER),
        "capabilities": [
            {
                "id": cap.id,
                "description": cap.description,
                "owner": cap.owner,
                "component": cap.component,
                "sensitivity": cap.sensitivity,
                "scope_kind": cap.scope_kind,
                "default_posture": cap.default_posture,
                "grant_at_state": cap.grant_at_state,
                "evidence": list(cap.evidence),
                "conformant_path": list(cap.conformant_path),
            }
            for cap in CAPABILITIES.values()
        ],
        "rights_scopes": dict(RIGHTS_SCOPE_FOR_CAPABILITY),
        "lifecycle_gate": dict(LIFECYCLE_GATE),
    }


def build_pointer() -> dict:
    return {
        "document": "admission.json",
        "version": VOCABULARY_VERSION,
        "authority": "orientation-only",
        "note": "Participant admission and capability orientation.",
    }


def _member_span(text: str, key: str) -> tuple[int, int] | None:
    """Locate the exact span of top-level member ``"key": <value>``."""
    marker = f'"{key}"'
    index = text.find(marker)
    if index < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    value_start = text.index(":", index) + 1
    start = value_start
    while start < len(text) and text[start] in " \t\n":
        start += 1
    pos = start
    while pos < len(text):
        char = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0:
                return index, pos + 1
        pos += 1
    return None


def render_member(key: str, value: dict, indent: str = "  ") -> str:
    body = json.dumps(value, indent=2, ensure_ascii=False)
    padded = "\n".join(
        (indent + line) if line.strip() else line for line in body.splitlines()
    )
    return f'{indent}"{key}": {padded.lstrip()}'


def sync(write: bool) -> list[str]:
    errors: list[str] = []
    try:
        text = SITE_ATLAS.read_text(encoding="utf-8")
        atlas = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read site/atlas.json: {exc}"]

    document = build_admission_document()
    pointer = build_pointer()

    # Full capability map lives in its own document.
    if SITE_ADMISSION.is_file():
        try:
            current_doc = json.loads(SITE_ADMISSION.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"cannot read site/admission.json: {exc}"]
    else:
        current_doc = None
    if current_doc != document:
        if not write:
            errors.append("site/admission.json drifts from admission.vocabulary")
        else:
            SITE_ADMISSION.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    # Core map carries only the pointer plus the shared schema version.
    if atlas.get("admission") != pointer:
        if not write:
            errors.append("site/atlas.json admission pointer drifts from admission.vocabulary")
        else:
            block = render_member("admission", pointer)
            span = _member_span(text, "admission")
            if span is not None:
                text = text[: span[0]] + block + text[span[1]:]
            else:
                anchor = '\n  "projects": ['
                if anchor not in text:
                    return ["cannot locate insertion anchor for admission pointer"]
                text = text.replace(anchor, "\n" + block + "," + anchor, 1)

    if atlas.get("schema_version") != VOCABULARY_VERSION:
        message = (
            f"schema_version {atlas.get('schema_version')!r} != "
            f"vocabulary {VOCABULARY_VERSION!r}"
        )
        if not write:
            errors.append(message)
        else:
            text = text.replace(
                f'"schema_version": "{atlas.get("schema_version")}"',
                f'"schema_version": "{VOCABULARY_VERSION}"',
                1,
            )
            atlas["schema_version"] = VOCABULARY_VERSION

    if write and not errors:
        SITE_ATLAS.write_text(text, encoding="utf-8")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify without writing")
    args = parser.parse_args()
    errors = sync(write=not args.check)
    if errors:
        print("admission sync failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("admission documents are in sync with admission.vocabulary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
