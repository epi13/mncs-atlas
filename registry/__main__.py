"""Command line entry point for the local Atlas registry."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .model import DEFAULT_OUTPUT, REGISTRY_DIR, RegistryError, build_registry, load_registry, read_json, write_json


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _find_project(registry: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    wanted = project_id.lower()
    for project in registry["projects"]:
        if project["id"] == wanted or wanted in project.get("aliases", []) or wanted in project.get("checkout_names", []):
            return project
    return None


def _find_capability(registry: dict[str, Any], capability_id: str) -> dict[str, Any] | None:
    wanted = capability_id.lower()
    for capability in registry["capabilities"]:
        if capability["id"] == wanted:
            return capability
    return None


def _identify_project(registry: dict[str, Any], path: Path) -> tuple[dict[str, Any] | None, str]:
    resolved = path.resolve()
    current = resolved if resolved.is_dir() else resolved.parent
    while True:
        manifest = current / ".mncs/project.json"
        if manifest.is_file():
            try:
                payload = read_json(manifest)
                if isinstance(payload, dict) and isinstance(payload.get("repository"), str):
                    project = _find_project(registry, payload["repository"])
                    if project:
                        return project, "repository-manifest"
            except RegistryError:
                pass
        if current.parent == current:
            break
        current = current.parent
    for project in registry["projects"]:
        for checkout_name in project.get("checkout_names", []):
            if resolved.name == checkout_name or resolved.name.lower() == checkout_name.lower():
                return project, "checkout-name"
    return None, "unresolved"


def _context(registry: dict[str, Any], path: Path) -> dict[str, Any]:
    project, identified_by = _identify_project(registry, path)
    if project is None:
        return {
            "schema_version": "mncs-atlas.context-capsule/v1",
            "surface_role": "orientation-only",
            "registry_revision": registry["registry_revision"],
            "registry_hash": registry["registry_hash"],
            "project": None,
            "identified_by": identified_by,
            "status": "UNKNOWN",
            "reason": f"No registered MNCS project matched {path.resolve()}",
        }
    project_id = project["id"]
    direct_edges = [edge for edge in registry["edges"] if edge["from"] == f"project:{project_id}" or edge["to"] == f"project:{project_id}"]
    dependencies = sorted(edge["to"].split(":", 1)[1] for edge in direct_edges if edge["from"] == f"project:{project_id}" and edge["kind"] == "depends_on")
    related: set[str] = set()
    for edge in direct_edges:
        endpoint = edge["to"] if edge["from"] == f"project:{project_id}" else edge["from"]
        if endpoint.startswith("project:") and endpoint != f"project:{project_id}":
            related.add(endpoint.split(":", 1)[1])
    canonical = sorted(
        capability["id"]
        for capability in registry["capabilities"]
        if capability.get("canonical_authority") == project_id
    )
    implementations = sorted(
        capability["id"]
        for capability in registry["capabilities"]
        if any(row["project"] == project_id and row["role"] in {"primary-implementation", "secondary-implementation", "experimental-implementation"} for row in capability["claims"])
    )
    consumers = sorted(
        capability["id"]
        for capability in registry["capabilities"]
        if any(row["project"] == project_id and row["role"] == "consumer" for row in capability["claims"])
    )
    relevant_authorities = sorted(
        {(
            capability["id"],
            capability["canonical_authority"],
        ) for capability in registry["capabilities"]
         if capability.get("canonical_authority") in dependencies}
    )
    relevant_decisions = sorted(
        decision["id"]
        for decision in registry["decisions"]
        if decision["owner"] == project_id or project_id in decision["affected_projects"] or any(capability in canonical + implementations + consumers for capability in decision["affected_capabilities"])
    )
    return {
        "schema_version": "mncs-atlas.context-capsule/v1",
        "surface_role": "orientation-only",
        "registry_revision": registry["registry_revision"],
        "registry_hash": registry["registry_hash"],
        "status": "PASS",
        "identified_by": identified_by,
        "project": {
            "id": project_id,
            "name": project["name"],
            "role": project["role"],
            "lifecycle": project["lifecycle"],
            "responsibility": project["responsibility"],
            "canonical_capabilities": canonical,
            "implemented_capabilities": implementations,
            "consumed_capabilities": consumers,
            "direct_family_dependencies": dependencies,
            "relevant_authorities": [
                {"capability": capability_id, "project": authority}
                for capability_id, authority in relevant_authorities
            ],
            "relevant_decisions": relevant_decisions,
            "closely_related_projects": sorted(related),
            "do_not_reimplement": sorted(project.get("non_goals", [])),
        },
    }


def _text_context(capsule: dict[str, Any]) -> str:
    if capsule.get("project") is None:
        return "\n".join(
            [
                "MNCS FAMILY CONTEXT",
                "Surface role: orientation-only; use Language Service for authoritative family preflight",
                f"Registry revision: {capsule['registry_revision']}",
                "Project: UNKNOWN",
                f"Reason: {capsule['reason']}",
                "Verify the repository identity before making cross-family changes.",
            ]
        )
    project = capsule["project"]
    def lines(values: list[str], empty: str = "none") -> list[str]:
        return [f"  {value}" for value in values] or [f"  {empty}"]
    authority_lines = [
        f"  {row['capability']} -> {row['project']}"
        for row in project["relevant_authorities"]
    ] or ["  none"]
    result = [
        "MNCS FAMILY CONTEXT",
        "Surface role: orientation-only; use Language Service for authoritative family preflight",
        f"Registry revision: {capsule['registry_revision']}",
        "",
        "Project:",
        f"  {project['id']}",
        f"  {project['responsibility']}",
        "",
        "Canonical responsibility:",
        *lines(project["canonical_capabilities"]),
        "",
        "Implemented capabilities:",
        *lines(project["implemented_capabilities"]),
        "",
        "Consumed capabilities:",
        *lines(project["consumed_capabilities"]),
        "",
        "Direct family dependencies:",
        *lines(project["direct_family_dependencies"]),
        "",
        "Relevant authorities:",
        *authority_lines,
        "",
        "Relevant decisions:",
        *lines(project["relevant_decisions"]),
        "",
        "Closely related projects:",
        *lines(sorted(project["closely_related_projects"])),
        "",
        "Do not reimplement:",
        *lines(project["do_not_reimplement"]),
    ]
    return "\n".join(result)


def _search(registry: dict[str, Any], query: str) -> list[dict[str, Any]]:
    terms = [term for term in re.findall(r"[a-z0-9-]+", query.lower()) if term]
    if not terms:
        return []
    results: list[tuple[int, str, dict[str, Any]]] = []
    for project in registry["projects"]:
        haystack = " ".join(str(project.get(field, "")) for field in ("id", "name", "role", "category", "responsibility", "non_goals")).lower()
        score = sum((3 if term == project["id"] else 0) + (2 if term in haystack else 0) for term in terms)
        if score:
            results.append((score, project["id"], {"kind": "project", "id": project["id"], "name": project["name"], "responsibility": project["responsibility"], "score": score}))
    for capability in registry["capabilities"]:
        haystack = " ".join(str(capability.get(field, "")) for field in ("id", "name", "description", "non_goals")).lower()
        score = sum((3 if term == capability["id"] else 0) + (2 if term in haystack else 0) for term in terms)
        if score:
            results.append((score, capability["id"], {"kind": "capability", "id": capability["id"], "name": capability["name"], "description": capability["description"], "score": score}))
    for decision in registry["decisions"]:
        haystack = " ".join(str(decision.get(field, "")) for field in ("id", "title", "summary", "affected_capabilities", "affected_projects")).lower()
        score = sum((3 if term == decision["id"].lower() else 0) + (2 if term in haystack else 0) for term in terms)
        if score:
            results.append((score, decision["id"], {"kind": "decision", "id": decision["id"], "title": decision["title"], "summary": decision["summary"], "score": score}))
    return [row for _, _, row in sorted(results, key=lambda item: (-item[0], item[1]))]


def _load_or_error(path: Path) -> dict[str, Any]:
    try:
        return load_registry(path)
    except RegistryError as error:
        print(f"atlas: {error}", file=sys.stderr)
        raise SystemExit(2) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mncs-atlas", description="Query the compiled MNCS family architecture graph")
    parser.add_argument("--registry", type=Path, default=DEFAULT_OUTPUT, help="compiled registry path")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="compile the deterministic family registry")
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument("--workspace-root", type=Path, action="append", default=[])
    build.add_argument("--manifest-snapshot", type=Path)
    validate = sub.add_parser("validate", help="validate a compiled registry")
    validate.add_argument("path", nargs="?", type=Path)
    validate.add_argument("--rebuild", action="store_true", help="rebuild inputs before validating")
    validate.add_argument("--fresh", action="store_true", help="compare the artifact with a fresh deterministic rebuild")
    for name, help_text in (("project", "show one project"), ("capability", "show one capability"), ("owner", "show capability ownership"), ("status", "show capability status"), ("decisions", "find indexed decisions"), ("related", "show directly related projects"), ("find", "search projects, capabilities, and decisions")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("query")
    context = sub.add_parser("context", help="emit a compact context capsule for a repository")
    context.add_argument("path", nargs="?", type=Path, default=Path("."))
    context.add_argument("--json", action="store_true")
    sync = sub.add_parser("sync", help="refresh pinned manifest snapshots from the MNCS standard checkout")
    sync.add_argument("--standard-root", type=Path, required=True)
    sync.add_argument("--output", type=Path, default=REGISTRY_DIR / "manifest-snapshot.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "sync":
            standard_root = args.standard_root.resolve()
            manifest_dir = standard_root / "family/manifests"
            if not manifest_dir.is_dir():
                raise RegistryError(f"standard checkout has no family/manifests directory: {manifest_dir}")
            manifests = []
            for path in sorted(manifest_dir.glob("*.json")):
                payload = read_json(path)
                errors = []
                from .model import validate_manifest

                errors.extend(validate_manifest(payload, str(path)))
                if errors:
                    raise RegistryError("invalid standard manifest:\n" + "\n".join(f"- {error}" for error in errors))
                manifests.append(payload)
            revision = "unknown"
            try:
                revision = subprocess.run(
                    ["git", "-C", str(standard_root), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except (OSError, subprocess.CalledProcessError):
                pass
            snapshot = {
                "schema_version": "mncs-atlas.manifest-snapshot/v1",
                "source": {
                    "repository": "machine-native-complexity-standard",
                    "path": "family/manifests",
                    "revision": revision,
                },
                "manifests": manifests,
            }
            write_json(args.output, snapshot)
            print(json.dumps({"status": "PASS", "output": str(args.output), "source_revision": revision, "manifests": len(manifests)}, sort_keys=True))
            return 0
        if args.command == "build":
            registry = build_registry(output=args.output, workspace_roots=args.workspace_root, manifest_snapshot=args.manifest_snapshot)
            print(json.dumps({"status": "PASS", "registry": str(args.output), "registry_revision": registry["registry_revision"], "projects": len(registry["projects"]), "capabilities": len(registry["capabilities"]), "decisions": len(registry["decisions"]), "edges": len(registry["edges"])}, sort_keys=True))
            return 0
        if args.command == "validate":
            path = args.path or args.registry
            if args.rebuild:
                build_registry(output=path)
            registry = _load_or_error(path)
            if args.fresh:
                fresh = build_registry(output=None)
                if fresh["registry_hash"] != registry["registry_hash"]:
                    print(
                        json.dumps(
                            {
                                "status": "STALE",
                                "artifact_revision": registry["registry_revision"],
                                "fresh_revision": fresh["registry_revision"],
                                "message": "compiled registry differs from current Atlas inputs; rebuild it",
                            },
                            sort_keys=True,
                        )
                    )
                    return 2
            print(json.dumps({"status": "PASS", "registry_revision": registry["registry_revision"], "fresh": args.fresh, "projects": len(registry["projects"]), "capabilities": len(registry["capabilities"]), "decisions": len(registry["decisions"]), "edges": len(registry["edges"])}, sort_keys=True))
            return 0
        registry = _load_or_error(args.registry)
        if args.command == "context":
            capsule = _context(registry, args.path)
            print(json.dumps(capsule, ensure_ascii=False, indent=2, sort_keys=True) if args.json else _text_context(capsule))
            return 0 if capsule["status"] == "PASS" else 2
        if args.command == "project":
            row = _find_project(registry, args.query)
            if row is None:
                print(f"atlas: unknown project {args.query!r}", file=sys.stderr)
                return 2
            _json(row)
            return 0
        if args.command in {"capability", "owner", "status"}:
            row = _find_capability(registry, args.query)
            if row is None:
                print(f"atlas: unknown capability {args.query!r}", file=sys.stderr)
                return 2
            if args.command == "owner":
                _json({"capability": row["id"], "ownership": row["ownership"], "canonical_authority": row["canonical_authority"], "claims": row["claims"]})
            elif args.command == "status":
                _json({"capability": row["id"], "status": "PASS" if row["canonical_authority"] else "UNKNOWN", "canonical_authority": row["canonical_authority"], "implementations": [claim["project"] for claim in row["claims"] if claim["role"] in {"primary-implementation", "secondary-implementation", "experimental-implementation"}], "consumers": [claim["project"] for claim in row["claims"] if claim["role"] == "consumer"]})
            else:
                _json(row)
            return 0
        if args.command == "decisions":
            query = args.query.lower()
            rows = [row for row in registry["decisions"] if query in json.dumps(row, ensure_ascii=False, sort_keys=True).lower()]
            _json(rows)
            return 0
        if args.command == "related":
            project = _find_project(registry, args.query)
            if project is None:
                print(f"atlas: unknown project {args.query!r}", file=sys.stderr)
                return 2
            project_node = f"project:{project['id']}"
            rows = [edge for edge in registry["edges"] if edge["from"] == project_node or edge["to"] == project_node]
            related = []
            for edge in rows:
                node = edge["to"] if edge["from"] == project_node else edge["from"]
                if node.startswith("project:") and node != project_node:
                    related.append({"project": node.split(":", 1)[1], "relationship": edge["kind"], "description": edge["description"]})
            _json(sorted(related, key=lambda row: (row["project"], row["relationship"])))
            return 0
        if args.command == "find":
            _json(_search(registry, args.query))
            return 0
        return 2
    except RegistryError as error:
        print(f"atlas: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
