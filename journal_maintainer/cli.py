"""Command-line surface for the Atlas Journal Maintainer."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .checkpoint import determine_checkpoint
from .config import load_config
from .models import RunOutcome
from .publication import check_changed_paths
from .gitops import evaluate_github_promotion
from .run import execute_run
from .validate import validate_site


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="journal_maintainer",
        description="Bounded Atlas Journal Maintainer for the MNCS Development Journal.",
    )
    parser.add_argument("--root", type=Path, default=None, help="Atlas repository root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Gather evidence, synthesize, and optionally publish")
    run.add_argument("--dry-run", action="store_true", help="Do not mutate the repository (default unless --publish/--prepare)")
    run.add_argument("--prepare", action="store_true", help="Write journal files locally without opening a PR")
    run.add_argument("--publish", action="store_true", help="Write, validate, branch, and open a PR from origin/main via a worktree")
    run.add_argument("--output-dir", type=Path, help="Write rendered HTML and run.json here")
    run.add_argument("--evidence-file", type=Path, help="Use recorded evidence instead of live GitHub")
    run.add_argument("--experiments-file", type=Path, help="Public experiment snapshot JSON")
    run.add_argument("--hints-file", type=Path, help="Optional conversation-hint JSON")
    run.add_argument("--draft-file", type=Path, help="Editor-supplied draft JSON, skipping heuristic synthesis")
    run.add_argument("--commons-url", help="Public Commons Agent Exchange base URL")
    run.add_argument("--synthesizer", default="heuristic", choices=["heuristic", "editor-draft"])
    run.add_argument("--mode", default="pr-only", choices=["dry-run", "editor-preview", "pr-only", "guarded-auto"], help="Operational rollout mode")
    run.add_argument("--now", help="Override current UTC time (ISO-8601)")
    run.add_argument("--retry", action="store_true", help="Mark the run as a retry of the current uncovered interval")
    run.add_argument("--json", action="store_true", help="Print the run record as JSON")

    sub.add_parser("checkpoint", help="Show the current uncovered interval")
    check = sub.add_parser("check-paths", help="Prove that changed paths are within the authorized journal surface")
    check.add_argument("--base", required=False, help="Trusted PR base revision (required for committed-diff CI checks)")
    check.add_argument("--head", default="HEAD", help="Exact PR head revision (default: HEAD)")
    sub.add_parser("validate", help="Run Atlas site and journal checks")
    finalize = sub.add_parser("finalize", help="Re-evaluate one PR after independent CI completes")
    finalize.add_argument("--pr-number", type=int, required=True)
    finalize.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = (args.root or Path.cwd()).resolve()
    if args.command == "checkpoint":
        checkpoint = determine_checkpoint(root / "site" / "journal")
        print(json.dumps(checkpoint.to_dict(), indent=2))
        return 0
    if args.command == "check-paths":
        result = check_changed_paths(root, base=args.base, head=args.head)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.allowed else 1
    if args.command == "validate":
        errors = validate_site(root)
        if errors:
            print("Journal Maintainer validation failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("Journal Maintainer and Atlas site validation passed.")
        return 0
    if args.command == "finalize":
        config = load_config(root, mode="guarded-auto")
        if not config.github_app_token:
            print(json.dumps({"eligible": False, "reasons": ["MNCS_JOURNAL_APP_TOKEN is absent; fail closed"]}, indent=2))
            return 2
        from .github_client import GitHubClient
        client = GitHubClient(config.github_app_token, api=config.github_api, user_agent=config.user_agent)
        pull = client.get_pull(config.owner, config.atlas_repo, args.pr_number)
        head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
        base = pull.get("base") if isinstance(pull.get("base"), dict) else {}
        base_sha = str(base.get("sha") or "")
        head_sha = str(head.get("sha") or "")
        try:
            path_check = check_changed_paths(root, base=base_sha, head=head_sha)
        except Exception as error:
            result = {"eligible": False, "reasons": [f"complete PR diff unavailable: {error}"]}
            print(json.dumps(result, indent=2))
            return 2
        eligibility = evaluate_github_promotion(client, config, pull, path_check=path_check, validation_ok=True, ambiguity=False)
        detail = eligibility.to_dict()
        detail["head_sha"] = head_sha
        if eligibility.eligible:
            enabled, message = client.enable_auto_merge(str(pull.get("node_id") or ""))
            detail["enabled"] = enabled
            detail["message"] = message
        else:
            detail["enabled"] = False
        body = str(pull.get("body") or "")
        marker = "### Independent Journal Finalizer"
        body = body.split(marker, 1)[0].rstrip() + f"\n\n{marker}\n\n- Head SHA: `{head_sha}`\n- Complete base→head diff: `{path_check.allowed}`\n- Automatic promotion eligible: `{eligibility.eligible}`\n- Reasons: {('; '.join(eligibility.reasons) or 'none')}\n"
        client.update_pull_request(config.owner, config.atlas_repo, args.pr_number, title=str(pull.get("title") or "journal"), body=body)
        print(json.dumps(detail, indent=2))
        return 0 if eligibility.eligible else 3

    now = None
    if args.now:
        text = args.now
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        now = datetime.fromisoformat(text)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
    config = load_config(
        root,
        commons_url=args.commons_url,
        experiments_file=args.experiments_file,
        hints_file=args.hints_file,
        evidence_file=args.evidence_file,
        synthesizer=args.synthesizer,
        mode=args.mode,
    )
    publish = bool(args.publish)
    dry_run = not args.prepare and not publish
    if args.dry_run:
        dry_run = True
        publish = False
    run = execute_run(
        config,
        now=now,
        dry_run=dry_run,
        publish=publish,
        output_dir=args.output_dir,
        draft_file=args.draft_file,
        retry=args.retry,
    )
    if args.json or args.output_dir:
        print(json.dumps(run.to_dict(), indent=2))
    else:
        _print_summary(run)
    if run.outcome in {RunOutcome.FAILED}:
        return 2
    if run.outcome == RunOutcome.AMBIGUOUS:
        return 3
    return 0


def _print_summary(run) -> None:
    print(f"Journal Maintainer run {run.run_id}")
    print(f"outcome: {run.outcome.value}")
    if run.covered:
        print(f"covered: {run.covered.start_date.isoformat()} → {run.covered.end_date.isoformat()}")
    if run.draft:
        print(f"entry: {run.draft.filename} — {run.draft.title}")
    if run.failure:
        print(f"failure: {run.failure.code}: {run.failure.message}")
    if run.pull_request_url:
        print(f"pull request: {run.pull_request_url}")
    if run.auto_merge:
        print(f"auto-merge eligible: {run.auto_merge.eligible}")
        if run.auto_merge.reasons:
            print("auto-merge reasons: " + "; ".join(run.auto_merge.reasons))
    for note in run.notes:
        print(f"note: {note}")


if __name__ == "__main__":
    raise SystemExit(main())
