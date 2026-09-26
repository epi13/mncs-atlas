"""Host-boundary source discovery for the Atlas projector.

This is the only module (besides ``render``) allowed to touch the
filesystem, network, or environment.  It decodes external data into a
typed source bundle and hands it to the pure ``project`` stage.  Every
source records a content identity and an availability status so missing
or unreadable inputs become explicit UNKNOWN downstream, never silent
gaps or fabricated facts.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Source:
    """One discovered input: identity, availability, and parsed payload."""

    id: str
    display_path: str
    content_sha256: str | None
    status: str  # present | missing | invalid
    reason: str
    payload: Any = None


@dataclass
class SourceBundle:
    """Everything the pure projection stage may consume."""

    atlas_root: Path
    workspace_root: Path
    commons_root: Path | None
    store_root: Path | None
    sources: list[Source] = field(default_factory=list)

    def by_id(self, source_id: str) -> Source | None:
        for source in self.sources:
            if source.id == source_id:
                return source
        return None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json_file(path: Path, source_id: str, display: str) -> Source:
    try:
        raw = path.read_bytes()
    except OSError:
        return Source(source_id, display, None, "missing", "file not present")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return Source(
            source_id, display, sha256_bytes(raw), "invalid", f"unparseable: {error}"
        )
    return Source(source_id, display, sha256_bytes(raw), "present", "readable", payload)


def _read_json_dir(
    directory: Path, source_id: str, display: str, suffix: str = ".json"
) -> Source:
    """Read a directory of JSON records as one hashed source."""
    if not directory.is_dir():
        return Source(source_id, display, None, "missing", "directory not present")
    files = sorted(
        path for path in directory.iterdir() if path.is_file() and path.name.endswith(suffix)
    )
    records: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    invalid = 0
    for path in files:
        try:
            raw = path.read_bytes()
            records.append({"file": path.name, "record": json.loads(raw.decode("utf-8"))})
            digest.update(path.name.encode("utf-8"))
            digest.update(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            invalid += 1
    reason = f"{len(records)} records"
    if invalid:
        reason += f"; {invalid} unreadable (excluded, not fabricated)"
    return Source(source_id, display, digest.hexdigest(), "present", reason, records)


def _default_roots(atlas_root: Path) -> tuple[Path, Path | None, Path | None]:
    workspace = Path(os.environ.get("MNCS_WORKSPACE_ROOT", atlas_root.parent)).resolve()
    commons = Path(os.environ.get("MNCS_COMMONS_ROOT", workspace / "MNCS-Commons"))
    store = Path(os.environ.get("MNCS_STORE_ROOT", workspace / "mncs-store"))
    return (
        workspace,
        commons if commons.is_dir() else None,
        store if store.is_dir() else None,
    )


def _workspace_manifests(workspace: Path) -> Source:
    """Discover sibling repository manifests without recursion.

    Top-level directories only, sorted by name: deterministic and bounded.
    A manifest that fails to parse is reported invalid; the repository is
    still listed as observed so the dashboard never hides it silently.
    """
    entries: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    try:
        candidates = sorted(path for path in workspace.iterdir() if path.is_dir())
    except OSError as error:
        return Source(
            "workspace-manifests", workspace.name, None, "invalid", f"unlistable: {error}"
        )
    for candidate in candidates:
        manifest = candidate / ".mncs" / "project.json"
        try:
            raw = manifest.read_bytes()
        except OSError:
            continue
        digest.update(candidate.name.encode("utf-8"))
        digest.update(raw)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            entries.append(
                {
                    "checkout": candidate.name,
                    "status": "invalid",
                    "reason": f"unparseable manifest: {error}",
                    "manifest": None,
                }
            )
            continue
        if not isinstance(payload, dict):
            entries.append(
                {
                    "checkout": candidate.name,
                    "status": "invalid",
                    "reason": "manifest is not a JSON object",
                    "manifest": None,
                }
            )
            continue
        entries.append(
            {
                "checkout": candidate.name,
                "status": "present",
                "reason": "repository-owned manifest",
                "manifest": payload,
            }
        )
    return Source(
        "workspace-manifests",
        f"{workspace.name}/*/.mncs/project.json",
        digest.hexdigest(),
        "present",
        f"{len(entries)} manifests discovered",
        entries,
    )


def _journal_head(atlas_root: Path) -> Source:
    events = atlas_root / "journal-events"
    entries: list[str] = []
    if events.is_dir():
        entries = sorted(
            path.name
            for path in events.iterdir()
            if path.is_file() and path.name.startswith("je-") and path.name.endswith(".json")
        )
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    latest = entries[-1] if entries else None
    return Source(
        "journal-head",
        "mncs-atlas/journal-events",
        digest,
        "present" if entries else "missing",
        f"{len(entries)} events" if entries else "no journal events published",
        {"count": len(entries), "latest": latest},
    )


def discover(
    atlas_root: Path | None = None,
    workspace_root: Path | None = None,
    commons_root: Path | None = None,
    store_root: Path | None = None,
) -> SourceBundle:
    """Collect every projection input with identity and availability."""
    atlas = (atlas_root or Path(__file__).resolve().parents[1]).resolve()
    default_workspace, default_commons, default_store = _default_roots(atlas)
    workspace = (workspace_root or default_workspace).resolve()
    commons = commons_root.resolve() if commons_root else default_commons
    store = store_root.resolve() if store_root else default_store

    bundle = SourceBundle(
        atlas_root=atlas,
        workspace_root=workspace,
        commons_root=commons,
        store_root=store,
    )
    push = bundle.sources.append
    push(
        _read_json_file(
            atlas / "registry" / "project-catalog.json",
            "atlas-catalog",
            "mncs-atlas/registry/project-catalog.json",
        )
    )
    push(
        _read_json_file(
            atlas / "registry" / "compiled.json",
            "atlas-compiled",
            "mncs-atlas/registry/compiled.json",
        )
    )
    push(_workspace_manifests(workspace))
    if commons is not None:
        family = commons / "family"
        push(
            _read_json_file(
                family / "participation-v1.json",
                "commons-participation",
                "MNCS-Commons/family/participation-v1.json",
            )
        )
        push(
            _read_json_file(
                family / "architecture-model-v1.json",
                "commons-architecture",
                "MNCS-Commons/family/architecture-model-v1.json",
            )
        )
        push(
            _read_json_file(
                family / "semantic-edges-v1.json",
                "commons-edges",
                "MNCS-Commons/family/semantic-edges-v1.json",
            )
        )
        push(
            _read_json_file(
                family / "architecture-delta-history-v1.json",
                "commons-deltas",
                "MNCS-Commons/family/architecture-delta-history-v1.json",
            )
        )
        push(
            _read_json_file(
                commons / "family-verification-checks-v1.json",
                "commons-verification",
                "MNCS-Commons/family-verification-checks-v1.json",
            )
        )
        push(
            _read_json_file(
                commons / "native-userland-status.json",
                "commons-native-status",
                "MNCS-Commons/native-userland-status.json",
            )
        )
        push(
            _read_json_dir(
                commons / "pressures" / "records", "commons-pressures", "MNCS-Commons/pressures/records"
            )
        )
    else:
        for source_id, display in (
            ("commons-participation", "MNCS-Commons/family/participation-v1.json"),
            ("commons-architecture", "MNCS-Commons/family/architecture-model-v1.json"),
            ("commons-edges", "MNCS-Commons/family/semantic-edges-v1.json"),
            ("commons-deltas", "MNCS-Commons/family/architecture-delta-history-v1.json"),
            ("commons-verification", "MNCS-Commons/family-verification-checks-v1.json"),
            ("commons-native-status", "MNCS-Commons/native-userland-status.json"),
            ("commons-pressures", "MNCS-Commons/pressures/records"),
        ):
            push(Source(source_id, display, None, "missing", "commons checkout not found"))
    if store is not None:
        push(
            _read_json_file(
                store / "family-verification-checks-v1.json",
                "store-verification",
                "mncs-store/family-verification-checks-v1.json",
            )
        )
        push(
            _read_json_file(
                store / "native-userland-status.json",
                "store-native-status",
                "mncs-store/native-userland-status.json",
            )
        )
    else:
        for source_id, display in (
            ("store-verification", "mncs-store/family-verification-checks-v1.json"),
            ("store-native-status", "mncs-store/native-userland-status.json"),
        ):
            push(Source(source_id, display, None, "missing", "store checkout not found"))
    push(_journal_head(atlas))
    return bundle
