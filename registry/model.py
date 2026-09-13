"""Deterministic MNCS family-registry model.

Atlas is an architectural memory, not a second implementation of a sibling
project.  Repository manifests provide compact contract facts.  The catalog,
capability claims, and decision index add only family-level ownership and
relationship semantics that cannot be inferred safely from a contract list.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "registry"
DEFAULT_OUTPUT = REGISTRY_DIR / "compiled.json"
MANIFEST_SCHEMA = "mncs-family.repository-manifest/v0alpha1"
REGISTRY_SCHEMA = "mncs-atlas.family-registry/v1"
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
VERSION_RE = re.compile(r"^v?[0-9A-Za-z][0-9A-Za-z.+_-]*$")
CLAIM_ROLES = {
    "canonical-authority",
    "primary-implementation",
    "secondary-implementation",
    "consumer",
    "experimental-implementation",
    "integration-layer",
}
LIFECYCLES = {"active", "incubating", "experimental", "orientation", "deprecated", "retired"}


class RegistryError(ValueError):
    """Raised when the family registry cannot be trusted."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RegistryError(f"unable to read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise RegistryError(f"invalid JSON in {path}: {error}") from error


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _string(value: Any, label: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty string")
        return None
    return value


def _string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{label} must be a list of non-empty strings")
        return []
    return list(value)


def validate_manifest(manifest: Any, origin: str = "manifest") -> list[str]:
    """Validate the stable v0alpha1 manifest subset used by Atlas.

    This mirrors the existing MNCS family-manifest contract without importing
    the standard repository at runtime.  Unknown extension fields are left to
    the owning schema validator; Atlas checks the high-confidence graph
    invariants it consumes.
    """

    errors: list[str] = []
    if not isinstance(manifest, dict):
        return [f"{origin} must contain a JSON object"]
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        errors.append(f"{origin}.schema_version must be {MANIFEST_SCHEMA}")
    repository = _string(manifest.get("repository"), f"{origin}.repository", errors)
    if repository is not None and not ID_RE.fullmatch(repository):
        errors.append(f"{origin}.repository is not a stable project id: {repository!r}")
    revision = manifest.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append(f"{origin}.revision must be a positive integer")
    if manifest.get("manifest_location", "in-repository") not in {"in-repository", "central"}:
        errors.append(f"{origin}.manifest_location is invalid")
    contracts = manifest.get("contracts")
    if not isinstance(contracts, dict):
        errors.append(f"{origin}.contracts must be an object")
        return errors
    for section in ("provides", "consumes", "tests"):
        if not isinstance(contracts.get(section), list):
            errors.append(f"{origin}.contracts.{section} must be a list")
    for index, item in enumerate(contracts.get("provides", [])):
        label = f"{origin}.contracts.provides[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        contract = _string(item.get("contract"), f"{label}.contract", errors)
        version = _string(item.get("version"), f"{label}.version", errors)
        _string(item.get("kind"), f"{label}.kind", errors)
        if item.get("stability") not in {"experimental", "stable", "deprecated", "retired"}:
            errors.append(f"{label}.stability is invalid")
        if version is not None and not VERSION_RE.fullmatch(version):
            errors.append(f"{label}.version is invalid: {version!r}")
        for field in ("fingerprint_sources", "consumers_declared"):
            if field in item:
                _string_list(item[field], f"{label}.{field}", errors)
        if contract is not None and not re.fullmatch(r"^[a-z][a-z0-9._-]*$", contract):
            errors.append(f"{label}.contract is invalid: {contract!r}")
    for index, item in enumerate(contracts.get("consumes", [])):
        label = f"{origin}.contracts.consumes[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        contract = _string(item.get("contract"), f"{label}.contract", errors)
        envelope = item.get("envelope")
        if not isinstance(envelope, dict) or envelope.get("op") not in {"any", "exact", "at-least", "compatible-minor"}:
            errors.append(f"{label}.envelope.op is invalid")
        if "required" not in item or not isinstance(item.get("required"), bool):
            errors.append(f"{label}.required must be boolean")
        if contract is not None and not re.fullmatch(r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9._-]*$", contract):
            errors.append(f"{label}.contract must be provider.contract: {contract!r}")
    for index, item in enumerate(contracts.get("tests", [])):
        label = f"{origin}.contracts.tests[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        _string(item.get("test"), f"{label}.test", errors)
        covers = _string_list(item.get("covers"), f"{label}.covers", errors)
        if not covers:
            errors.append(f"{label}.covers must not be empty")
        if item.get("obligation") not in {"self", "consumer-compatibility", "family-integration"}:
            errors.append(f"{label}.obligation is invalid")
        command = item.get("command")
        if command is not None and (
            not isinstance(command, dict)
            or not isinstance(command.get("argv"), list)
            or not command["argv"]
            or any(not isinstance(arg, str) for arg in command["argv"])
        ):
            errors.append(f"{label}.command.argv must be a non-empty string list")
    return errors


def _normalized_id(value: str, aliases: Mapping[str, str]) -> str:
    return aliases.get(value, value)


def _load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != "mncs-atlas.project-catalog/v1":
        raise RegistryError(f"{path} is not an Atlas project catalog v1")
    rows = raw.get("projects")
    if not isinstance(rows, list):
        raise RegistryError(f"{path}.projects must be a list")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise RegistryError(f"{path}.projects[{index}] has no stable id")
        project_id = row["id"]
        if project_id in result:
            raise RegistryError(f"{path} duplicates project {project_id}")
        result[project_id] = row
    return result


def _load_claims(path: Path) -> list[dict[str, Any]]:
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != "mncs-atlas.capability-claims/v1":
        raise RegistryError(f"{path} is not an Atlas capability-claims v1 document")
    claims = raw.get("capabilities")
    if not isinstance(claims, list):
        raise RegistryError(f"{path}.capabilities must be a list")
    return claims


def _load_decisions(path: Path) -> list[dict[str, Any]]:
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != "mncs-atlas.decision-index/v1":
        raise RegistryError(f"{path} is not an Atlas decision-index v1 document")
    decisions = raw.get("decisions")
    if not isinstance(decisions, list):
        raise RegistryError(f"{path}.decisions must be a list")
    return decisions


def _snapshot_manifests(path: Path) -> list[tuple[dict[str, Any], str]]:
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != "mncs-atlas.manifest-snapshot/v1":
        raise RegistryError(f"{path} is not an Atlas manifest snapshot v1")
    manifests = raw.get("manifests")
    if not isinstance(manifests, list):
        raise RegistryError(f"{path}.manifests must be a list")
    return [(manifest, f"{path}#manifests[{index}]") for index, manifest in enumerate(manifests)]


def _discover_local_manifests(roots: Iterable[Path]) -> list[tuple[dict[str, Any], str]]:
    found: list[tuple[dict[str, Any], str]] = []
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if root.is_file() and root.name == "project.json":
            candidates = [root]
        elif root.is_dir():
            candidates = sorted(root.rglob(".mncs/project.json"))
        else:
            candidates = []
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            found.append((read_json(path), str(path)))
    return found


def _manifest_contracts(manifest: Mapping[str, Any], aliases: Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    provides: list[dict[str, Any]] = []
    consumes: list[dict[str, Any]] = []
    source_id = str(manifest["repository"])
    provider = _normalized_id(source_id, aliases)
    for item in manifest["contracts"]["provides"]:
        identity = f"{provider}.{item['contract']}/{item['version']}"
        provides.append(
            {
                "id": identity,
                "contract": item["contract"],
                "version": item["version"],
                "kind": item["kind"],
                "stability": item["stability"],
                "fingerprint_sources": sorted(item.get("fingerprint_sources", [])),
            }
        )
    for item in manifest["contracts"]["consumes"]:
        contract = item["contract"]
        provider_name, contract_name = contract.split(".", 1)
        consumes.append(
            {
                "contract": f"{_normalized_id(provider_name, aliases)}.{contract_name}",
                "envelope": dict(item["envelope"]),
                "required": item["required"],
                "evidence_refs": sorted(item.get("evidence_refs", [])),
            }
        )
    return provides, consumes


def _source_digest(manifest: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(manifest))


def _profile_status(declared: Any, current: str | None) -> str:
    if declared is None:
        return "not-declared"
    if not isinstance(declared, str) or not re.fullmatch(r"\d+\.\d+", declared):
        return "invalid"
    if current is None or not re.fullmatch(r"\d+\.\d+", current):
        return "unknown-current"
    declared_parts = tuple(int(part) for part in declared.split("."))
    current_parts = tuple(int(part) for part in current.split("."))
    if declared_parts == current_parts:
        return "current"
    return "legacy" if declared_parts < current_parts else "future"


def _project_record(
    project_id: str,
    catalog: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
    manifest_origin: str | None,
    aliases: Mapping[str, str],
    current_language_profile: str | None,
) -> dict[str, Any]:
    record = {
        "id": project_id,
        "name": catalog.get("name", project_id),
        "repository": catalog.get("repository", f"https://github.com/epi13/{project_id}"),
        "role": catalog.get("role", "family-project"),
        "category": catalog.get("category", "research"),
        "lifecycle": catalog.get("lifecycle", "experimental"),
        "authority_class": catalog.get("authority_class", "non-normative"),
        "responsibility": catalog.get("responsibility", "Declared by the owning repository."),
        "non_goals": sorted(catalog.get("non_goals", [])),
        "language_profile": catalog.get("language_profile"),
        "language_profile_status": _profile_status(catalog.get("language_profile"), current_language_profile),
        "dependencies": sorted({_normalized_id(item, aliases) for item in catalog.get("dependencies", [])}),
        "checkout_names": sorted(set(catalog.get("checkout_names", [project_id]))),
        "aliases": sorted(alias for alias, target in aliases.items() if target == project_id),
        "manifest": None,
    }
    if manifest is not None:
        provides, consumes = _manifest_contracts(manifest, aliases)
        if ".mncs/project.json" in (manifest_origin or ""):
            stable_origin = "repository:.mncs/project.json"
        elif "#manifests[" in (manifest_origin or ""):
            stable_origin = "pinned-snapshot:manifest-snapshot.json"
        else:
            stable_origin = manifest_origin
        record["manifest"] = {
            "schema_version": manifest["schema_version"],
            "revision": manifest["revision"],
            "location": manifest.get("manifest_location", "in-repository"),
            "origin": stable_origin,
            "sha256": _source_digest(manifest),
            "provides": provides,
            "consumes": consumes,
            "tests": sorted(item["test"] for item in manifest["contracts"]["tests"]),
        }
    return record


def _edge(source: str, target: str, kind: str, description: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {
        "from": source,
        "to": target,
        "kind": kind,
        "description": description,
        "evidence": sorted(evidence or []),
    }


def _cycle(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[str] | None:
    graph: dict[str, list[str]] = {node: [] for node in nodes}
    for source, target in edges:
        graph.setdefault(source, []).append(target)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: list[str]) -> list[str] | None:
        if node in visiting:
            start = trail.index(node) if node in trail else 0
            return trail[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        for child in sorted(graph.get(node, [])):
            result = visit(child, trail + [node])
            if result:
                return result
        visiting.remove(node)
        visited.add(node)
        return None

    for node in sorted(graph):
        result = visit(node, [])
        if result:
            return result
    return None


def build_registry(
    *,
    root: Path = ROOT,
    output: Path | None = DEFAULT_OUTPUT,
    workspace_roots: Iterable[Path] = (),
    manifest_snapshot: Path | None = None,
) -> dict[str, Any]:
    """Compile catalog + manifests + claims + decisions into one artifact."""

    root = root.resolve()
    registry_dir = root / "registry"
    catalog_path = registry_dir / "project-catalog.json"
    claims_path = registry_dir / "capability-claims.json"
    decisions_path = registry_dir / "decisions.json"
    snapshot_path = manifest_snapshot or registry_dir / "manifest-snapshot.json"
    catalog = _load_catalog(catalog_path)
    claims = _load_claims(claims_path)
    decisions = _load_decisions(decisions_path)
    config = read_json(registry_dir / "config.json")
    aliases = config.get("project_aliases", {}) if isinstance(config, dict) else {}
    central_aliases = config.get("central_manifest_aliases", {}) if isinstance(config, dict) else {}
    if not isinstance(aliases, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in aliases.items()):
        raise RegistryError("registry/config.json project_aliases must be a string map")
    if not isinstance(central_aliases, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in central_aliases.items()):
        raise RegistryError("registry/config.json central_manifest_aliases must be a string map")
    local_roots = [root / ".mncs/project.json", *workspace_roots]
    raw_manifests = _snapshot_manifests(snapshot_path) + _discover_local_manifests(local_roots)
    selected: dict[str, tuple[dict[str, Any], str, bool]] = {}
    source_digests: dict[str, Any] = {
        "project_catalog": _source_digest(read_json(catalog_path)),
        "capability_claims": _source_digest(read_json(claims_path)),
        "decisions": _source_digest(read_json(decisions_path)),
        "manifest_snapshot": _source_digest(read_json(snapshot_path)),
        "manifests": {},
    }
    errors: list[str] = []
    for manifest, origin in raw_manifests:
        errors.extend(validate_manifest(manifest, origin))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("repository"), str):
            continue
        is_local = "#manifests[" not in origin and ".mncs/project.json" in origin
        raw_id = manifest["repository"]
        project_id = raw_id if is_local else _normalized_id(raw_id, {**aliases, **central_aliases})
        source_digests["manifests"][project_id] = _source_digest(manifest)
        existing = selected.get(project_id)
        if existing is None or (is_local and not existing[2]):
            selected[project_id] = (manifest, origin, is_local)
        elif existing[0] != manifest:
            errors.append(
                f"conflicting manifests for {project_id}: {existing[1]} and {origin}; "
                "only a repository-local manifest may supersede the pinned snapshot"
            )
    for project_id, row in catalog.items():
        if not ID_RE.fullmatch(project_id):
            errors.append(f"catalog project id is invalid: {project_id!r}")
        if row.get("lifecycle", "experimental") not in LIFECYCLES:
            errors.append(f"catalog project {project_id} has invalid lifecycle")
    unknown_catalog_manifests = sorted(set(selected) - set(catalog))
    for project_id in unknown_catalog_manifests:
        errors.append(f"manifest {project_id} has no project catalog entry")
    missing_manifest = sorted(project_id for project_id in catalog if project_id not in selected and catalog[project_id].get("manifest_required", True))
    for project_id in missing_manifest:
        errors.append(f"project {project_id} is missing a manifest (local or pinned snapshot)")
    projects = []
    current_language_profile = config.get("current_language_profile")
    if not isinstance(current_language_profile, str):
        errors.append("registry/config.json current_language_profile must be a string")
        current_language_profile = None
    for project_id in sorted(catalog):
        manifest_info = selected.get(project_id)
        manifest_aliases = aliases if manifest_info is not None and manifest_info[2] else {**aliases, **central_aliases}
        projects.append(
            _project_record(
                project_id,
                catalog[project_id],
                manifest_info[0] if manifest_info else None,
                manifest_info[1] if manifest_info else None,
                manifest_aliases,
                current_language_profile,
            )
        )
    project_ids = {project["id"] for project in projects}
    capabilities: list[dict[str, Any]] = []
    capability_ids_seen: set[str] = set()
    edges: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("id"), str):
            errors.append("capability claim without an id")
            continue
        capability_id = claim["id"]
        if capability_id in capability_ids_seen:
            errors.append(f"duplicate capability id: {capability_id}")
        capability_ids_seen.add(capability_id)
        if not ID_RE.fullmatch(capability_id):
            errors.append(f"capability id is invalid: {capability_id!r}")
        ownership = claim.get("ownership", "shared")
        if ownership not in {"exclusive", "shared"}:
            errors.append(f"capability {capability_id} has invalid ownership mode")
        rows = claim.get("claims")
        if not isinstance(rows, list) or not rows:
            errors.append(f"capability {capability_id} must have at least one claim")
            rows = []
        canonical = [row for row in rows if isinstance(row, dict) and row.get("role") == "canonical-authority"]
        if ownership == "exclusive" and len(canonical) != 1:
            errors.append(f"exclusive capability {capability_id} must have exactly one canonical authority")
        normalized_rows = []
        for row in rows:
            if not isinstance(row, dict):
                errors.append(f"capability {capability_id} contains a non-object claim")
                continue
            project_id = _normalized_id(str(row.get("project", "")), aliases)
            role = row.get("role")
            if project_id not in project_ids:
                errors.append(f"capability {capability_id} references unknown project {project_id}")
            if role not in CLAIM_ROLES:
                errors.append(f"capability {capability_id} has invalid claim role {role!r}")
            project = next((item for item in projects if item["id"] == project_id), None)
            if project and project["lifecycle"] in {"deprecated", "retired"} and role == "canonical-authority":
                errors.append(f"superseded project {project_id} still claims canonical authority for {capability_id}")
            normalized = {
                "project": project_id,
                "role": role,
                "status": row.get("status", "active"),
                "evidence": sorted(row.get("evidence", [])),
                "note": row.get("note", ""),
            }
            normalized_rows.append(normalized)
            kind = {
                "canonical-authority": "canonical_for",
                "primary-implementation": "implements",
                "secondary-implementation": "implements",
                "consumer": "consumes",
                "experimental-implementation": "experiments_with",
                "integration-layer": "integrates",
            }.get(role, "relates_to")
            edges.append(
                _edge(
                    f"project:{project_id}",
                    f"capability:{capability_id}",
                    kind,
                    row.get("note", f"{project_id} declares a {role} relationship to {capability_id}."),
                    row.get("evidence", []),
                )
            )
        capabilities.append(
            {
                "id": capability_id,
                "name": claim.get("name", capability_id),
                "description": claim.get("description", ""),
                "ownership": ownership,
                "canonical_authority": _normalized_id(canonical[0]["project"], aliases) if len(canonical) == 1 else None,
                "claims": sorted(normalized_rows, key=lambda row: (row["project"], row["role"])),
                "non_goals": sorted(claim.get("non_goals", [])),
            }
        )
        if len(canonical) == 1:
            canonical_project = _normalized_id(canonical[0]["project"], aliases)
            edges.append(
                _edge(
                    f"capability:{capability_id}",
                    f"project:{canonical_project}",
                    "owned_by",
                    "Canonical authority claim; Atlas does not confer external authority.",
                    canonical[0].get("evidence", []),
                )
            )
    capability_ids = {capability["id"] for capability in capabilities}
    for project in projects:
        source = f"project:{project['id']}"
        for dependency in project["dependencies"]:
            if dependency not in project_ids:
                errors.append(f"project {project['id']} depends on unknown project {dependency}")
            else:
                edges.append(_edge(source, f"project:{dependency}", "depends_on", "Declared direct family dependency."))
        manifest = project.get("manifest") or {}
        for provided in manifest.get("provides", []):
            edges.append(_edge(source, f"contract:{provided['id']}", "provides", "Repository manifest provides this contract."))
        for consumed in manifest.get("consumes", []):
            provider = consumed["contract"].split(".", 1)[0]
            if provider not in project_ids:
                errors.append(f"project {project['id']} consumes contract from unknown project {provider}")
            edges.append(_edge(source, f"contract:{consumed['contract']}", "consumes", "Repository manifest consumes this contract."))
    dependency_edges = [(project["id"], dep) for project in projects for dep in project["dependencies"]]
    cycle = _cycle(project_ids, dependency_edges)
    if cycle:
        errors.append("dependency cycle: " + " -> ".join(cycle))
    normalized_decisions: list[dict[str, Any]] = []
    decision_ids: set[str] = set()
    for index, decision in enumerate(decisions):
        label = f"decision[{index}]"
        if not isinstance(decision, dict) or not isinstance(decision.get("id"), str):
            errors.append(f"{label} has no id")
            continue
        decision_id = decision["id"]
        if decision_id in decision_ids:
            errors.append(f"duplicate decision id: {decision_id}")
        decision_ids.add(decision_id)
        owner = _normalized_id(str(decision.get("owner", "")), aliases)
        if owner not in project_ids:
            errors.append(f"decision {decision_id} references unknown owner {owner}")
        affected_projects = sorted({_normalized_id(str(item), aliases) for item in decision.get("affected_projects", [])})
        for affected in affected_projects:
            if affected not in project_ids:
                errors.append(f"decision {decision_id} references unknown affected project {affected}")
        affected_capabilities = sorted(set(decision.get("affected_capabilities", [])))
        for capability_id in affected_capabilities:
            if capability_id not in capability_ids:
                errors.append(f"decision {decision_id} references unknown capability {capability_id}")
        row = {
            "id": decision_id,
            "title": decision.get("title", ""),
            "owner": owner,
            "source": dict(decision.get("source", {})),
            "status": decision.get("status", "active"),
            "affected_capabilities": affected_capabilities,
            "affected_projects": affected_projects,
            "supersedes": decision.get("supersedes"),
            "summary": decision.get("summary", ""),
        }
        normalized_decisions.append(row)
        edges.append(_edge(f"decision:{decision_id}", f"project:{owner}", "owned_by", "Decision remains owned by its source repository.", [row["source"].get("path", "")]))
        for capability_id in affected_capabilities:
            edges.append(_edge(f"decision:{decision_id}", f"capability:{capability_id}", "governs", "Indexed affected capability."))
        for affected in affected_projects:
            edges.append(_edge(f"decision:{decision_id}", f"project:{affected}", "applies_to", "Indexed affected project."))
        if row["supersedes"]:
            if row["supersedes"] not in decision_ids and not any(item.get("id") == row["supersedes"] for item in decisions):
                errors.append(f"decision {decision_id} supersedes unknown decision {row['supersedes']}")
            edges.append(_edge(f"decision:{decision_id}", f"decision:{row['supersedes']}", "supersedes", "Decision lifecycle relationship."))
    normalized_decisions.sort(key=lambda row: row["id"])
    capabilities.sort(key=lambda row: row["id"])
    edges.sort(key=lambda row: (row["from"], row["kind"], row["to"], row["description"]))
    content = {
        "schema_version": REGISTRY_SCHEMA,
        "registry_id": config.get("registry_id", "mncs-family"),
        "authority": {
            "kind": "architecture-and-ownership-graph",
            "does_not_create": [
                "conformance",
                "certification",
                "independent evidence",
                "Commons pressure status",
                "runtime application authority",
            ],
            "note": "Atlas records declared family architecture; owning repositories and external authorities retain semantic authority.",
        },
        "source_contracts": {
            "repository_manifest": MANIFEST_SCHEMA,
            "commons": "external-pressure-source; schema intentionally not pinned during this campaign",
        },
        "projects": projects,
        "capabilities": capabilities,
        "decisions": normalized_decisions,
        "edges": edges,
        "exclusions": config.get("exclusions", []),
        "source_digests": source_digests,
    }
    registry_hash = sha256_bytes(canonical_bytes(content))
    result = {**content, "registry_hash": registry_hash, "registry_revision": registry_hash[:16]}
    if errors:
        raise RegistryError("registry build failed:\n" + "\n".join(f"- {error}" for error in sorted(set(errors))))
    if output is not None:
        write_json(output, result)
    return result


def validate_registry(registry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if registry.get("schema_version") != REGISTRY_SCHEMA:
        errors.append(f"schema_version must be {REGISTRY_SCHEMA}")
    projects = registry.get("projects")
    capabilities = registry.get("capabilities")
    decisions = registry.get("decisions")
    edges = registry.get("edges")
    if not isinstance(projects, list) or not projects:
        errors.append("projects must be a non-empty list")
        projects = []
    if not isinstance(capabilities, list):
        errors.append("capabilities must be a list")
        capabilities = []
    if not isinstance(decisions, list):
        errors.append("decisions must be a list")
        decisions = []
    if not isinstance(edges, list):
        errors.append("edges must be a list")
        edges = []
    project_ids = [row.get("id") for row in projects if isinstance(row, dict)]
    if len(project_ids) != len(set(project_ids)):
        errors.append("duplicate project id")
    capability_ids = [row.get("id") for row in capabilities if isinstance(row, dict)]
    if len(capability_ids) != len(set(capability_ids)):
        errors.append("duplicate capability id")
    decision_ids = {row.get("id") for row in decisions if isinstance(row, dict)}
    known_nodes = {f"project:{item}" for item in project_ids}
    known_nodes |= {f"capability:{item}" for item in capability_ids}
    known_nodes |= {f"decision:{item}" for item in decision_ids}
    known_contracts: set[str] = set()
    for project in projects:
        manifest = project.get("manifest") or {}
        for item in manifest.get("provides", []):
            known_contracts.add(f"contract:{item['id']}")
        for item in manifest.get("consumes", []):
            known_contracts.add(f"contract:{item['contract']}")
    known_nodes |= known_contracts
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"edge[{index}] must be an object")
            continue
        unknown_endpoints = [endpoint for endpoint in (edge.get("from"), edge.get("to")) if endpoint not in known_nodes]
        for endpoint in unknown_endpoints:
            errors.append(f"edge[{index}] has an unknown endpoint: {endpoint!r}")
        if edge.get("from") == edge.get("to"):
            errors.append(f"edge[{index}] self-references")
    if [row.get("id") for row in projects if isinstance(row, dict)] != sorted(project_ids):
        errors.append("projects are not in deterministic id order")
    if [row.get("id") for row in capabilities if isinstance(row, dict)] != sorted(capability_ids):
        errors.append("capabilities are not in deterministic id order")
    if [row.get("id") for row in decisions if isinstance(row, dict)] != sorted(decision_ids):
        errors.append("decisions are not in deterministic id order")
    edge_order = [
        (row.get("from"), row.get("kind"), row.get("to"), row.get("description"))
        for row in edges
        if isinstance(row, dict)
    ]
    if edge_order != sorted(edge_order):
        errors.append("edges are not in deterministic order")
    expected_hash = registry.get("registry_hash")
    body = {key: value for key, value in registry.items() if key not in {"registry_hash", "registry_revision"}}
    if isinstance(expected_hash, str) and expected_hash != sha256_bytes(canonical_bytes(body)):
        errors.append("registry_hash does not match canonical registry content")
    return errors


def load_registry(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = read_json(path)
    if not isinstance(value, dict):
        raise RegistryError(f"{path} must contain a registry object")
    errors = validate_registry(value)
    if errors:
        raise RegistryError(f"invalid compiled registry {path}:\n" + "\n".join(f"- {error}" for error in errors))
    return value
