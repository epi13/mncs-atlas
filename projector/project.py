"""Pure dashboard projection: source bundle -> bounded projection payload.

No I/O.  The same source bundle always produces the same payload bytes,
so the semantic hash doubles as the no-change identity for publication.
Content identity reuses the registry's canonical bytes: one definition of
"same meaningful input" across Atlas, not two.
"""

from __future__ import annotations

import hashlib
from typing import Any

from registry.model import canonical_bytes

from . import PROJECTION_SCHEMA
from .discover import SourceBundle
from .rules import (
    authority_note,
    classify_implementation,
    freshness_state,
    maturity_note,
    normalize_lifecycle,
    stable_key,
    verification_state,
)

MAX_LISTED_PRESSURES = 100


def semantic_hash(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _payload(source: Any) -> Any:
    return source.payload if source is not None and source.status == "present" else None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _project_ecosystem(bundle: SourceBundle) -> dict[str, Any]:
    catalog = _as_dict(_payload(bundle.by_id("atlas-catalog")))
    catalog_projects = {
        str(entry.get("id")): entry
        for entry in _as_list(catalog.get("projects"))
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    manifests = _as_list(_payload(bundle.by_id("workspace-manifests")))
    by_checkout = {str(row.get("checkout")): row for row in manifests if isinstance(row, dict)}
    by_repo_name = {}
    for row in manifests:
        if not isinstance(row, dict):
            continue
        manifest = _as_dict(row.get("manifest"))
        name = manifest.get("repository")
        if isinstance(name, str):
            by_repo_name.setdefault(name, row)
    participation = _as_dict(_payload(bundle.by_id("commons-participation")))
    participation_by_id = {
        str(entry.get("id")): entry
        for entry in _as_list(participation.get("projects"))
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }

    projects: list[dict[str, Any]] = []
    for project_id in sorted(set(catalog_projects) | set(by_repo_name)):
        entry = catalog_projects.get(project_id, {})
        observed = by_repo_name.get(project_id)
        manifest = _as_dict(observed.get("manifest")) if observed else {}
        part = participation_by_id.get(project_id, {})
        lifecycle = normalize_lifecycle(entry.get("lifecycle"))
        authority = authority_note(entry.get("authority_class"))
        maturity = maturity_note(entry.get("maturity"))
        manifest_info: dict[str, Any] | None = None
        if observed is not None:
            manifest_info = {
                "checkout": observed.get("checkout"),
                "status": observed.get("status"),
                "origin": "repository:.mncs/project.json"
                if observed.get("status") == "present"
                else None,
                "revision": manifest.get("revision"),
                "reason": observed.get("reason"),
            }
        participation_info: dict[str, Any] | None = None
        if part:
            participation_info = {
                "state": part.get("state", "unknown"),
                "reason": part.get("reason"),
            }
        projects.append(
            {
                "id": project_id,
                "name": _text(entry.get("name")) or _text(manifest.get("repository")) or project_id,
                "category": _text(entry.get("category")) or "unknown",
                "purpose": _text(entry.get("responsibility")) or "unknown",
                "role": _text(entry.get("role")) or "unknown",
                "lifecycle": lifecycle["lifecycle"],
                "lifecycle_reason": lifecycle["reason"],
                "authority_class": authority["authority_class"],
                "authority_reason": authority["reason"],
                "maturity": maturity["maturity"],
                "maturity_reason": maturity["reason"],
                "repository": _text(entry.get("repository")),
                "dependencies": sorted(
                    str(item) for item in _as_list(entry.get("dependencies")) if item
                ),
                "observed_in_workspace": observed is not None
                and observed.get("status") == "present",
                "manifest": manifest_info,
                "participation": participation_info,
            }
        )
    observed_only = sorted(
        str(row.get("checkout"))
        for row in manifests
        if isinstance(row, dict)
        and row.get("status") == "present"
        and str(_as_dict(row.get("manifest")).get("repository", "")) not in catalog_projects
    )
    return {
        "project_count": len(projects),
        "projects": projects,
        "observed_but_uncatalogued": observed_only,
        "catalog_description": _text(catalog.get("description")),
    }


def _project_relationships(bundle: SourceBundle) -> dict[str, Any]:
    edges_source = bundle.by_id("commons-edges")
    edges_payload = _as_dict(_payload(edges_source))
    edges = []
    for edge in _as_list(edges_payload.get("edges")):
        if not isinstance(edge, dict):
            continue
        edges.append(
            {
                "producer": edge.get("producer_repository"),
                "consumer": edge.get("consumer_repository"),
                "contract": edge.get("contract_identity"),
                "contract_revision": edge.get("contract_revision"),
                "provenance": edge.get("provenance"),
            }
        )
    edges.sort(key=lambda item: (str(item["producer"]), str(item["consumer"]), str(item["contract"])))
    compiled = _as_dict(_payload(bundle.by_id("atlas-compiled")))
    return {
        "commons_edges": edges,
        "commons_edge_count": len(edges),
        "commons_limitations": list(edges_payload.get("limitations", [])),
        "commons_complete": edges_payload.get("complete"),
        "atlas_registry": {
            "status": bundle.by_id("atlas-compiled").status if bundle.by_id("atlas-compiled") else "missing",
            "registry_revision": compiled.get("registry_revision"),
            "registry_hash": compiled.get("registry_hash"),
            "project_count": len(_as_list(compiled.get("projects"))),
            "capability_count": len(_as_list(compiled.get("capabilities"))),
            "edge_count": len(_as_list(compiled.get("edges"))),
            "decision_count": len(_as_list(compiled.get("decisions"))),
        },
    }


def _project_capabilities(bundle: SourceBundle) -> dict[str, Any]:
    architecture = _as_dict(_payload(bundle.by_id("commons-architecture")))
    capabilities = []
    for capability in _as_list(architecture.get("capabilities")):
        if not isinstance(capability, dict):
            continue
        canonical = _as_dict(capability.get("canonical"))
        classification = _as_dict(canonical.get("classification"))
        capabilities.append(
            {
                "id": capability.get("id"),
                "owner": capability.get("owner"),
                "kind": canonical.get("kind"),
                "lifecycle": classification.get("lifecycle", "unknown"),
                "alternates": _as_list(capability.get("active_alternates")),
            }
        )
    capabilities.sort(key=lambda item: str(item["id"]))
    generators = []
    for generator in _as_list(architecture.get("generators")):
        if not isinstance(generator, dict):
            continue
        generators.append(
            {
                "id": generator.get("id"),
                "owner": generator.get("owner"),
                "classification": generator.get("classification"),
            }
        )
    generators.sort(key=lambda item: str(item["id"]))
    return {
        "capabilities": capabilities,
        "capability_count": len(capabilities),
        "generators": generators,
        "policy": architecture.get("policy"),
    }


def _project_implementation(bundle: SourceBundle) -> dict[str, Any]:
    declarations = []
    for source_id in ("commons-native-status", "store-native-status"):
        source = bundle.by_id(source_id)
        payload = _as_dict(_payload(source))
        if not payload:
            declarations.append(
                {
                    "source": source_id,
                    "status": source.status if source else "missing",
                    "reason": source.reason if source else "no source",
                    "classification": classify_implementation(None),
                }
            )
            continue
        declarations.append(
            {
                "source": source_id,
                "status": "present",
                "repository_id": payload.get("repository_id"),
                "declared_status": payload.get("status"),
                "canonical_entrypoint": payload.get("canonical_entrypoint"),
                "native_source_count": len(_as_dict(payload.get("native_sources"))),
                "classification": classify_implementation(payload.get("status")),
                "note": "repository-level declaration; no per-project implementation states are declared anywhere",
            }
        )
    return {
        "declarations": declarations,
        "per_project_states": "unknown",
        "per_project_reason": "no per-project implementation declarations exist in any source",
    }


def _project_pressures(bundle: SourceBundle) -> dict[str, Any]:
    source = bundle.by_id("commons-pressures")
    records = _payload(source)
    if not isinstance(records, list):
        return {
            "status": source.status if source else "missing",
            "reason": source.reason if source else "no source",
            "total": 0,
            "by_repository": {},
            "by_status": {},
            "listed": [],
            "truncated": False,
        }
    by_repository: dict[str, int] = {}
    by_status: dict[str, int] = {}
    listed = []
    for row in records:
        if not isinstance(row, dict):
            continue
        record = _as_dict(row.get("record"))
        status = str(record.get("status", record.get("initialStatus", "unknown")))
        by_status[status] = by_status.get(status, 0) + 1
        repos = record.get("affectedRepositories") or []
        if not isinstance(repos, list) or not repos:
            by_repository.setdefault("undeclared", 0)
            by_repository["undeclared"] += 1
        for repo in repos:
            key = str(repo)
            by_repository[key] = by_repository.get(key, 0) + 1
        listed.append(
            {
                "id": record.get("id", row.get("file")),
                "repositories": sorted(str(repo) for repo in repos) if isinstance(repos, list) else [],
                "capability": record.get("capability"),
                "domain": record.get("domain"),
                "status": status,
                "severity": record.get("severity"),
                "title": record.get("title") or record.get("summary"),
                "content_digest": record.get("contentDigest"),
            }
        )
    listed.sort(key=stable_key)
    truncated = len(listed) > MAX_LISTED_PRESSURES
    return {
        "status": "present",
        "reason": source.reason if source else "",
        "total": len(listed),
        "by_repository": dict(sorted(by_repository.items())),
        "by_status": by_status,
        "listed": listed[:MAX_LISTED_PRESSURES],
        "truncated": truncated,
        "lifecycle_note": "records carry discovery state only; no resolution lifecycle is tracked in the record schema",
    }


def _project_verification(bundle: SourceBundle) -> dict[str, Any]:
    declared = []
    for source_id in ("commons-verification", "store-verification"):
        source = bundle.by_id(source_id)
        payload = _as_dict(_payload(source))
        for check in _as_list(payload.get("checks")):
            if not isinstance(check, dict):
                continue
            state = verification_state(check)
            declared.append(
                {
                    "source": source_id,
                    "repository_id": payload.get("repository_id"),
                    "identity": check.get("identity"),
                    "contract": check.get("contract_identity"),
                    "runner": check.get("runner"),
                    "surface": check.get("surface"),
                    "state": state["state"],
                    "reason": state["reason"],
                }
            )
    declared.sort(key=lambda item: (str(item["source"]), str(item["identity"])))
    return {
        "declared_checks": declared,
        "declared_count": len(declared),
        "banner": "declarations without a result feed: every check is UNKNOWN until an owning verifier publishes results",
    }


def _project_movement(bundle: SourceBundle) -> dict[str, Any]:
    deltas_payload = _as_dict(_payload(bundle.by_id("commons-deltas")))
    deltas = []
    for delta in _as_list(deltas_payload.get("deltas")):
        if not isinstance(delta, dict):
            continue
        deltas.append(
            {
                "previous": delta.get("previous_content_identity"),
                "current": delta.get("current_content_identity"),
                "changed_capabilities": sorted(
                    str(item) for item in _as_list(delta.get("changed_capabilities"))
                ),
                "added_contracts": sorted(str(item) for item in _as_list(delta.get("added_contracts"))),
                "removed_contracts": sorted(
                    str(item) for item in _as_list(delta.get("removed_contracts"))
                ),
                "ownership_changes": _as_list(delta.get("ownership_changes")),
            }
        )
    return {
        "deltas": deltas,
        "delta_count": len(deltas),
        "retention": deltas_payload.get("retention"),
        "note": "machine-recorded architecture movement only; Git history is not reproduced",
    }


def project(bundle: SourceBundle) -> dict[str, Any]:
    """Build the full projection payload (timestamps excluded)."""
    sources = [
        {
            "id": source.id,
            "path": "workspace/*/.mncs/project.json"
            if source.id == "workspace-manifests"
            else source.display_path,
            "content_sha256": source.content_sha256,
            "status": source.status,
            "reason": source.reason,
        }
        for source in bundle.sources
    ]
    payload = {
        "schema_version": PROJECTION_SCHEMA,
        "sources": sources,
        "freshness": freshness_state([source.status for source in bundle.sources]),
        "ecosystem": _project_ecosystem(bundle),
        "relationships": _project_relationships(bundle),
        "capabilities": _project_capabilities(bundle),
        "implementation": _project_implementation(bundle),
        "pressures": _project_pressures(bundle),
        "verification": _project_verification(bundle),
        "movement": _project_movement(bundle),
        "journal": {
            "note": "the dashboard is deterministic current state; interpretation lives in the Journal",
            **_as_dict(_payload(bundle.by_id("journal-head"))),
        },
    }
    payload["semantic_hash"] = semantic_hash(payload)
    return payload
