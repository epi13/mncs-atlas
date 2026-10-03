"""Ambient semantic entry points for Atlas projections (repo-owned renderers).

Each ``render_*`` function receives the semantic state model (values already
observed through declared subjects) and returns content. No filesystem
reads, no workspace rescans: the model is the renderer's whole world. The
pure ``project``/``validate``/``sanitize`` stages are shared unchanged with
the manual ``discover -> project -> render`` CLI path; only the source
bundle is assembled from observed values instead of a live rescan.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

CHECKOUT = Path(__file__).resolve().parents[1]

from projector.discover import Source, SourceBundle
from projector.project import project
from projector.render import envelope, envelope_bytes, noscript_table
from projector.validate import sanitize, validate
from registry.model import build_registry, canonical_bytes


def _model_source(model: dict[str, Any], slot: str) -> dict[str, Any] | None:
    for entry in model.get("sources", []):
        if isinstance(entry, dict) and entry.get("slot") == slot:
            return entry
    return None


def _hex_identity(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _file_source(source_id: str, display: str, model: dict[str, Any], slot: str) -> Source:
    """Rebuild one file source from its observed value and availability."""
    entry = _model_source(model, slot) or {}
    status = entry.get("status", "missing")
    value = model.get("values", {}).get(slot)
    if status == "present":
        return Source(source_id, display, _hex_identity(value), "present",
                      "readable", value)
    if status == "invalid":
        return Source(source_id, display, None, "invalid", "unparseable subject")
    return Source(source_id, display, None, "missing", "file not present")


def _manifests_source(model: dict[str, Any]) -> Source:
    """Rebuild the family-manifest bundle from wildcard expansion rows."""
    rows = model.get("values", {}).get("manifests")
    if rows is None:
        return Source("workspace-manifests", "workspace/*/.mncs/project.json",
                      None, "missing", "no repositories in expansion scope")
    entries = [
        {"checkout": row.get("repository"), "status": row.get("status"),
         "reason": row.get("reason"),
         "manifest": row.get("value") if row.get("status") == "present" else None}
        for row in rows if isinstance(row, dict)
    ]
    return Source("workspace-manifests", "workspace/*/.mncs/project.json",
                  _hex_identity(entries), "present",
                  "%d manifests observed" % len(entries), entries)


def _journal_source(model: dict[str, Any]) -> Source:
    """Rebuild the journal head from observed event-record names.

    Only ``je-*.json`` records count, exactly like the manual
    ``discover`` journal head; other directory members are ignored.
    """
    rows = model.get("values", {}).get("journal") or []
    names = sorted(row["file"] for row in rows
                   if isinstance(row, dict) and isinstance(row.get("file"), str)
                   and row["file"].startswith("je-"))
    digest = hashlib.sha256("\n".join(names).encode("utf-8")).hexdigest()
    payload: dict[str, Any] = {"count": len(names), "latest": names[-1] if names else None}
    if names:
        return Source("journal-head", "mncs-atlas/journal-events", digest,
                      "present", "%d events" % len(names), payload)
    return Source("journal-head", "mncs-atlas/journal-events", digest,
                  "missing", "no journal events published", payload)


def _pressures_source(model: dict[str, Any]) -> Source:
    """Rebuild the pressures record source from observed directory rows."""
    rows = model.get("values", {}).get("pressures")
    if rows is None:
        return Source("commons-pressures", "MNCS-Commons/pressures/records",
                      None, "missing", "directory not present")
    entry = _model_source(model, "pressures") or {}
    return Source("commons-pressures", "MNCS-Commons/pressures/records",
                  _hex_identity(rows), "present",
                  str(entry.get("reason") or "%d records" % len(rows)), rows)


def bundle_from_model(model: dict[str, Any]) -> SourceBundle:
    """Assemble the pure projection bundle from observed semantic values."""
    # Roots are bundle metadata only; the pure stage consumes sources.
    bundle = SourceBundle(atlas_root=CHECKOUT, workspace_root=CHECKOUT,
                          commons_root=None, store_root=None)
    push = bundle.sources.append
    push(_file_source("atlas-catalog", "mncs-atlas/registry/project-catalog.json",
                      model, "catalog"))
    push(_file_source("atlas-compiled", "mncs-atlas/registry/compiled.json",
                      model, "compiled"))
    push(_manifests_source(model))
    for source_id, slot, display in (
            ("commons-participation", "participation",
             "MNCS-Commons/family/participation-v1.json"),
            ("commons-architecture", "architecture",
             "MNCS-Commons/family/architecture-model-v1.json"),
            ("commons-edges", "edges",
             "MNCS-Commons/family/semantic-edges-v1.json"),
            ("commons-deltas", "deltas",
             "MNCS-Commons/family/architecture-delta-history-v1.json"),
            ("commons-verification", "verification",
             "MNCS-Commons/family-verification-checks-v1.json"),
            ("commons-native-status", "native_status",
             "MNCS-Commons/native-userland-status.json")):
        push(_file_source(source_id, display, model, slot))
    push(_pressures_source(model))
    push(_file_source("store-verification",
                      "mncs-store/family-verification-checks-v1.json",
                      model, "store_verification"))
    push(_file_source("store-native-status",
                      "mncs-store/native-userland-status.json",
                      model, "store_native_status"))
    push(_journal_source(model))
    return bundle


def _dashboard_payload(model: dict[str, Any]) -> dict[str, Any]:
    payload = project(bundle_from_model(model))
    errors = validate(payload)
    if errors:
        raise ValueError("dashboard projection invalid: " + "; ".join(errors[:5]))
    return sanitize(payload)


def _observed_identities(model: dict[str, Any]) -> dict[str, str]:
    return {str(entry.get("slot")): str(entry.get("identity"))
            for entry in model.get("sources", [])
            if isinstance(entry, dict) and entry.get("slot")}


def render_dashboard(model: dict[str, Any]) -> str:
    """Render site/dashboard.json content (envelope bytes as text)."""
    payload = _dashboard_payload(model)
    data = envelope(payload, source_epoch=model.get("identity"),
                    observed=_observed_identities(model))
    return envelope_bytes(data).decode("utf-8")


def render_noscript(model: dict[str, Any]) -> str:
    """Render the dashboard.html noscript region content."""
    payload = _dashboard_payload(model)
    return "\n<noscript>\n" + noscript_table(payload) + "\n</noscript>\n"


def render_registry(model: dict[str, Any]) -> str:
    """Render registry/compiled.json content from observed registry inputs."""
    values = model.get("values", {})
    manifest = values.get("own_manifest")
    live = [(manifest, "repository:.mncs/project.json")] if manifest is not None else []
    result = build_registry(
        root=CHECKOUT, output=None, live_manifests=live,
        inputs={"catalog": values.get("catalog"),
                "claims": values.get("claims"),
                "decisions": values.get("decisions"),
                "snapshot": values.get("snapshot"),
                "config": values.get("config")})
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def _registry_page_render():
    path = CHECKOUT / "scripts" / "render_registry_page.py"
    spec = importlib.util.spec_from_file_location("atlas_render_registry_page", path)
    if spec is None or spec.loader is None:
        raise ValueError("registry page renderer not loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render


def render_registry_page(model: dict[str, Any]) -> str:
    """Render site/registry.html content from the compiled registry."""
    compiled = model.get("values", {}).get("compiled")
    if not isinstance(compiled, dict):
        raise ValueError("registry page requires the compiled registry value")
    return _registry_page_render()(compiled)
