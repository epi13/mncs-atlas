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
        base_ref = f"origin/{base}"
        if run_git(root, "rev-parse", "--verify", base_ref, check=False).returncode == 0 and run_git(
            root, "merge-base", "--is-ancestor", base_ref, name, check=False
        ).returncode != 0:
            raise GitError(f"existing branch {name} is not based on trusted {base_ref}")
        run_git(root, "checkout", name)
        return
    remote = run_git(root, "rev-parse", "--verify", f"origin/{name}", check=False)
    if remote.returncode == 0:
        base_ref = f"origin/{base}"
        if run_git(root, "rev-parse", "--verify", base_ref, check=False).returncode == 0 and run_git(
            root, "merge-base", "--is-ancestor", base_ref, f"origin/{name}", check=False
        ).returncode != 0:
            raise GitError(f"remote branch {name} is not based on trusted {base_ref}")
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
    required_checks_ok: bool | None = True,
    head_sha: str | None = None,
    evaluated_head_sha: str | None = None,
    origin_verified: bool = True,
) -> AutoMergeEligibility:
    reasons: list[str] = []
    if not originated_from_maintainer:
        reasons.append("PR did not originate from the Journal Maintainer path")
    if not origin_verified:
        reasons.append("PR branch/actor provenance could not be verified")
    if not path_check.allowed:
        reasons.append("unexpected paths changed: " + ", ".join(path_check.unexpected))
    if not validation_ok:
        reasons.append("Atlas validation did not pass")
    if ambiguity:
        reasons.append("material evidence ambiguity requires human review")
    if mergeable_state != "clean":
        reasons.append(f"PR mergeable_state={mergeable_state or 'UNKNOWN'} is not CLEAN")
    if reviews_request_changes:
        reasons.append("human review requested changes")
    if human_hold:
        reasons.append("human hold is present")
    if required_checks_ok is not True:
        reasons.append("required Atlas checks have not succeeded for this exact head SHA")
    if head_sha and evaluated_head_sha and head_sha != evaluated_head_sha:
        reasons.append("head SHA changed after the decision was evaluated")
    if repo_allows_auto_merge is False:
        reasons.append("repository settings do not permit auto-merge")
    elif repo_allows_auto_merge is None:
        reasons.append("repository auto-merge setting could not be confirmed")
    return AutoMergeEligibility(
        eligible=not reasons,
        reasons=reasons,
        repository_permits_auto_merge=repo_allows_auto_merge,
    )


def verify_maintainer_provenance(
    pull: dict, *, owner: str, repo: str, branch: str, app_slug: str | None = None
) -> bool:
    """Verify repository/branch identity; labels and names are not authority."""
    head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    full_name = str(head_repo.get("full_name") or head.get("label") or "")
    expected = f"{owner}/{repo}"
    actor = pull.get("user") if isinstance(pull.get("user"), dict) else {}
    login = str(actor.get("login") or "")
    actor_type = str(actor.get("type") or "")
    bot_identity = login == app_slug or (actor_type == "Bot" and login.endswith("[bot]"))
    return (
        str(head.get("ref") or "") == branch
        and (full_name == expected or full_name == f"{owner}:{branch}")
        and bot_identity
        and bool(pull.get("head", {}).get("sha"))
    )


def evaluate_github_promotion(
    client: GitHubClient,
    config: MaintainerConfig,
    pull: dict,
    *,
    path_check: PathCheckResult,
    validation_ok: bool,
    ambiguity: bool,
) -> AutoMergeEligibility:
    """Fetch current GitHub state and evaluate a single immutable head snapshot."""
    number = pull.get("number")
    if not isinstance(number, int):
        return AutoMergeEligibility(False, ["pull request number is missing"])
    current = client.pull_status(config.owner, config.atlas_repo, number)
    head = current.get("head") if isinstance(current.get("head"), dict) else {}
    sha = str(head.get("sha") or "")
    branch = str(head.get("ref") or "")
    if not sha:
        return AutoMergeEligibility(False, ["exact PR head SHA could not be confirmed"])
    reviews = client.pull_reviews(config.owner, config.atlas_repo, number)
    requested = any(
        str(review.get("state") or "").upper() == "CHANGES_REQUESTED"
        for review in reviews
        if isinstance(review, dict)
    )
    labels = {
        str(label.get("name") or "").lower()
        for label in (current.get("labels") or [])
        if isinstance(label, dict)
    }
    hold = bool(labels.intersection({"human-hold", "journal-maintainer:hold", "hold"}))
    checks = client.check_runs(config.owner, config.atlas_repo, sha)
    statuses = client.combined_status(config.owner, config.atlas_repo, sha)
    check_success = bool(checks) and all(
        str(check.get("status") or "").lower() == "completed"
        and str(check.get("conclusion") or "").lower() == "success"
        for check in checks
    )
    protection = client.branch_protection(
        config.owner,
        config.atlas_repo,
        str((current.get("base") if isinstance(current.get("base"), dict) else {}).get("ref") or config.base_branch),
    )
    required_block = protection.get("required_status_checks") if isinstance(protection, dict) else None
    required_contexts = [
        str(context) for context in (required_block.get("contexts") or [])
    ] if isinstance(required_block, dict) else []
    check_names = {str(check.get("name") or "") for check in checks}
    status_names = {str(status.get("context") or "") for status in (statuses.get("statuses") or []) if isinstance(status, dict)}
    required_present = bool(required_contexts) and all(
        context in check_names or context in status_names or any(context in name for name in check_names)
        for context in required_contexts
    )
    # Missing/unknown combined status or unconfigured required checks is not
    # success; promotion is fail-closed.
    status_success = str(statuses.get("state") or "").lower() == "success"
    required_ok = check_success and status_success and required_present
    settings = client.repo_settings(config.owner, config.atlas_repo)
    allowed = settings.get("allow_auto_merge")
    origin_ok = verify_maintainer_provenance(
        current, owner=config.owner, repo=config.atlas_repo, branch=branch, app_slug=getattr(config, "github_app_slug", None)
    ) and MAINTAINER_LABEL in {str(label.get("name") or "") for label in current.get("labels") or [] if isinstance(label, dict)}
    return evaluate_auto_merge(
        originated_from_maintainer=origin_ok,
        origin_verified=origin_ok,
        path_check=path_check,
        validation_ok=validation_ok,
        ambiguity=ambiguity,
        mergeable_state=str(current.get("mergeable_state") or "UNKNOWN").lower(),
        reviews_request_changes=requested,
        repo_allows_auto_merge=allowed if isinstance(allowed, bool) else None,
        human_hold=hold,
        required_checks_ok=required_ok,
        head_sha=sha,
        evaluated_head_sha=sha,
    )


def try_enable_auto_merge(client: GitHubClient, pull: dict) -> tuple[bool, str]:
    node_id = pull.get("node_id")
    if not node_id:
        return False, "pull request node_id missing"
    return client.enable_auto_merge(str(node_id))
