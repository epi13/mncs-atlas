"""Maintainer configuration.

Defaults keep Atlas dependency-free and fail closed. Optional endpoints are
adapters over public contracts, never sibling internals.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .models import FamilyProject

DEFAULT_OWNER = "epi13"
DEFAULT_ATLAS_REPO = "mncs-atlas"
DEFAULT_BASE_BRANCH = "main"
CANONICAL_PAGES_URL = "https://epi13.github.io/mncs-atlas/"

# Public operator repositories that Atlas marks deployment-private in the
# orientation map but that still have inspectable GitHub history.
EXTRA_PUBLIC_REPOSITORIES = ("epi13/mncs-control-mcp",)


@dataclass
class MaintainerConfig:
    root: Path
    owner: str = DEFAULT_OWNER
    atlas_repo: str = DEFAULT_ATLAS_REPO
    base_branch: str = DEFAULT_BASE_BRANCH
    github_token: str | None = None
    # Where the API token came from. Only an explicit Journal Maintainer App
    # token may act as the App identity; a local operator credential (gh CLI,
    # GITHUB_TOKEN) is recorded here so provenance never conflates them.
    github_token_source: str | None = None
    github_api: str = "https://api.github.com"
    commons_url: str | None = None
    commons_allow_http: bool = False
    experiments_file: Path | None = None
    hints_file: Path | None = None
    evidence_file: Path | None = None
    # Exported MNCS Control journal-context bundle (schema
    # mncs-control.journal-context.v1). This is the bounded local operator
    # context surface: Control supplies evidence; Atlas keeps editorial
    # semantics. The bundle is untrusted data, never instructions.
    journal_context_file: Path | None = None
    synthesizer: str = "heuristic"
    mode: str = "pr-only"
    github_app_token: str | None = None
    github_app_slug: str | None = None
    user_agent: str = "mncs-atlas-journal-maintainer/0.1"
    extra_repositories: tuple[str, ...] = EXTRA_PUBLIC_REPOSITORIES

    @property
    def site(self) -> Path:
        return self.root / "site"

    @property
    def journal_dir(self) -> Path:
        return self.site / "journal"

    @property
    def atlas_json(self) -> Path:
        return self.site / "atlas.json"

    @property
    def sitemap(self) -> Path:
        return self.site / "sitemap.xml"


def load_config(
    root: Path | None = None,
    *,
    github_token: str | None = None,
    commons_url: str | None = None,
    experiments_file: Path | None = None,
    hints_file: Path | None = None,
    evidence_file: Path | None = None,
    journal_context_file: Path | None = None,
    synthesizer: str = "heuristic",
    mode: str = "pr-only",
    allow_gh_cli_token: bool = True,
) -> MaintainerConfig:
    resolved_root = (root or Path.cwd()).resolve()
    app_token = os.environ.get("MNCS_JOURNAL_APP_TOKEN") or os.environ.get("MNCS_JOURNAL_GITHUB_APP_TOKEN")
    token = github_token or app_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    token_source = "explicit" if github_token else ("app" if app_token else ("env" if token else None))
    if token is None and allow_gh_cli_token:
        # Interactive/operator fallback: reuse an already-authenticated `gh`
        # session so local runs do not needlessly degrade to anonymous GitHub
        # API access. This credential is a user identity, never the Journal
        # Maintainer App identity, and it is never logged.
        discovered = _gh_cli_token()
        if discovered:
            token = discovered
            token_source = "gh-cli"
    commons = commons_url or os.environ.get("MNCS_COMMONS_URL")
    experiments = experiments_file
    if experiments is None and os.environ.get("MNCS_EXPERIMENT_SNAPSHOT"):
        experiments = Path(os.environ["MNCS_EXPERIMENT_SNAPSHOT"])
    hints = hints_file
    if hints is None and os.environ.get("MNCS_JOURNAL_HINTS"):
        hints = Path(os.environ["MNCS_JOURNAL_HINTS"])
    context = journal_context_file
    if context is None and os.environ.get("MNCS_JOURNAL_CONTEXT_FILE"):
        context = Path(os.environ["MNCS_JOURNAL_CONTEXT_FILE"])
    return MaintainerConfig(
        root=resolved_root,
        github_token=token,
        github_token_source=token_source,
        commons_url=commons,
        commons_allow_http=os.environ.get("MNCS_COMMONS_ALLOW_HTTP") == "1",
        experiments_file=experiments,
        hints_file=hints,
        evidence_file=evidence_file,
        journal_context_file=context,
        synthesizer=synthesizer,
        mode=mode,
        github_app_token=app_token,
        github_app_slug=os.environ.get("MNCS_JOURNAL_APP_SLUG"),
    )


def _gh_cli_token() -> str | None:
    """Return the current `gh` CLI access token without logging its value."""

    executable = shutil.which("gh")
    if not executable:
        return None
    try:
        completed = subprocess.run(
            [executable, "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    token = (completed.stdout or "").strip()
    if not token or len(token) > 512 or any(char.isspace() for char in token):
        return None
    return token


def parse_github_repo(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def load_family_projects(config: MaintainerConfig) -> list[FamilyProject]:
    atlas = json.loads(config.atlas_json.read_text(encoding="utf-8"))
    projects: list[FamilyProject] = []
    seen: set[tuple[str, str]] = set()

    def add(component: dict, *, operator: bool) -> None:
        repository = component.get("repository")
        parsed = parse_github_repo(repository)
        owner = repo = None
        if parsed:
            owner, repo = parsed
            if (owner, repo) in seen:
                return
            seen.add((owner, repo))
        projects.append(
            FamilyProject(
                project_id=str(component.get("id") or repo or component.get("name") or "unknown"),
                name=str(component.get("name") or component.get("id") or "unknown"),
                repository=repository,
                owner=owner,
                repo=repo,
                role=str(component.get("role") or ""),
                maturity=component.get("maturity"),
                authority_class=component.get("authority_class"),
                operator=operator,
            )
        )

    for component in atlas.get("projects") or []:
        if isinstance(component, dict):
            add(component, operator=False)
    for component in atlas.get("operator_components") or []:
        if isinstance(component, dict):
            add(component, operator=True)
    for extra in config.extra_repositories:
        owner, repo = extra.split("/", 1)
        if (owner, repo) in seen:
            continue
        seen.add((owner, repo))
        projects.append(
            FamilyProject(
                project_id=repo,
                name=repo,
                repository=f"https://github.com/{owner}/{repo}",
                owner=owner,
                repo=repo,
                role="operator-implementation",
                operator=True,
            )
        )
    return projects
