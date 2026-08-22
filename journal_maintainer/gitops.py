"""Git/GitHub publication operations.

Control may invoke these via the Atlas CLI. GitHub remains the promotion
mechanism. The maintainer never force-pushes, never force-merges, and never
circumvents branch protection.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .config import MaintainerConfig
from .github_client import GitHubClient
from .http import HttpError
from .models import AutoMergeEligibility, MAINTAINER_LABEL, PathCheckResult
from .sanitize import safe_branch_name


class GitError(RuntimeError):
    pass


def run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise GitError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result


def create_or_reuse_branch(root: Path, branch: str, base: str) -> None:
    name = safe_branch_name(branch)
    run_git(root, "fetch", "origin", base, check=False)
    existing = run_git(root, "rev-parse", "--verify", name, check=False)
    if existing.returncode == 0:
        run_git(root, "checkout", name)
        return
    remote = run_git(root, "rev-parse", "--verify", f"origin/{name}", check=False)
    if remote.returncode == 0:
        run_git(root, "checkout", "-B", name, f"origin/{name}")
        return
    start = f"origin/{base}"
    if run_git(root, "rev-parse", "--verify", start, check=False).returncode != 0:
        start = base
    run_git(root, "checkout", "-B", name, start)


def commit_authorized_paths(root: Path, paths: list[str], message: str) -> str | None:
    if not paths:
        return None
    run_git(root, "add", "--", *paths)
    status = run_git(root, "status", "--porcelain")
    if not status.stdout.strip():
        return None
    run_git(root, "commit", "-m", message)
    sha = run_git(root, "rev-parse", "HEAD").stdout.strip()
    return sha


def push_branch(root: Path, branch: str) -> None:
    run_git(root, "push", "-u", "origin", branch)


def open_or_update_pull_request(
    client: GitHubClient,
    config: MaintainerConfig,
    *,
    branch: str,
    title: str,
    body: str,
) -> dict:
    existing = client.find_pull_request(config.owner, config.atlas_repo, branch, config.base_branch)
    if existing and existing.get("number"):
        updated = client.update_pull_request(
            config.owner,
            config.atlas_repo,
            int(existing["number"]),
            title=title,
            body=body,
        )
        client.add_labels(config.owner, config.atlas_repo, int(existing["number"]), [MAINTAINER_LABEL])
        return updated or existing
    created = client.create_pull_request(
        config.owner,
        config.atlas_repo,
        title=title,
        body=body,
        head=branch,
        base=config.base_branch,
    )
    number = created.get("number")
    if isinstance(number, int):
        client.add_labels(config.owner, config.atlas_repo, number, [MAINTAINER_LABEL])
    return created


def evaluate_auto_merge(
    *,
    originated_from_maintainer: bool,
    path_check: PathCheckResult,
    validation_ok: bool,
    ambiguity: bool,
    mergeable_state: str | None,
    reviews_request_changes: bool,
    repo_allows_auto_merge: bool | None,
    human_hold: bool,
) -> AutoMergeEligibility:
    reasons: list[str] = []
    if not originated_from_maintainer:
        reasons.append("PR did not originate from the Journal Maintainer path")
    if not path_check.allowed:
        reasons.append("unexpected paths changed: " + ", ".join(path_check.unexpected))
    if not validation_ok:
        reasons.append("Atlas validation did not pass")
    if ambiguity:
        reasons.append("material evidence ambiguity requires human review")
    if mergeable_state in {"dirty", "blocked"}:
        reasons.append(f"PR mergeable_state={mergeable_state}")
    if reviews_request_changes:
        reasons.append("human review requested changes")
    if human_hold:
        reasons.append("human hold is present")
    if repo_allows_auto_merge is False:
        reasons.append("repository settings do not permit auto-merge")
    elif repo_allows_auto_merge is None:
        reasons.append("repository auto-merge setting could not be confirmed")
    return AutoMergeEligibility(
        eligible=not reasons,
        reasons=reasons,
        repository_permits_auto_merge=repo_allows_auto_merge,
    )


def try_enable_auto_merge(client: GitHubClient, pull: dict) -> tuple[bool, str]:
    node_id = pull.get("node_id")
    if not node_id:
        return False, "pull request node_id missing"
    return client.enable_auto_merge(str(node_id))
