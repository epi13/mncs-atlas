#!/usr/bin/env python3
"""Deterministic Atlas refresh controller: safe local refresh to publication.

Local cycle (default)::

    lock -> tree safety -> registry build -> projection -> registry page
        -> Pages mirror sync -> site checks -> no-change report

Publication (``--publish``) additionally makes a narrowly scoped
deterministic commit of generated files only, then pushes the current
branch.  Merging to ``main`` stays a human/PR decision.

``--check`` is a dry run: discover, project, and validate without writing
anything into the working tree.

No timestamps enter committed output: the dashboard envelope carries only
the observed semantic epoch, and the no-change gate compares semantic
hashes, so re-running an unchanged world leaves the tree (and history)
untouched.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STATE_DIR = Path.home() / ".local" / "share" / "mncs-atlas"
LOCK_PATH = STATE_DIR / "refresh.lock"
LOG_PATH = STATE_DIR / "refresh.log"

# Files the controller may regenerate.  Anything else dirty refuses the run.
GENERATED = (
    "registry/compiled.json",
    "site/registry.html",
    "registry.html",
    "site/dashboard.html",
    "dashboard.html",
    "site/dashboard.json",
    "dashboard.json",
)

SERVICE_NAME = "mncs-atlas-refresh"


def run(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=check)


def status_line(message: str) -> dict[str, str]:
    print(message, flush=True)
    return {"ok": message}


def git_porcelain() -> list[str]:
    completed = run("git", "status", "--porcelain")
    return [line for line in completed.stdout.splitlines() if line.strip()]


def dirty_outside_generated() -> list[str]:
    offenders = []
    for line in git_porcelain():
        path = line[3:] if len(line) > 3 else line
        path = path.split(" -> ")[-1].strip().strip('"')
        if path not in GENERATED:
            offenders.append(line)
    return offenders


def head_dashboard_hash() -> str | None:
    completed = run("git", "show", "HEAD:site/dashboard.json", check=False)
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout).get("semantic_hash")
    except (json.JSONDecodeError, AttributeError):
        return None


def cmd_check() -> int:
    from projector.discover import discover
    from projector.project import project
    from projector.validate import validate

    bundle = discover(atlas_root=ROOT)
    payload = project(bundle)
    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"check: invalid: {error}", file=sys.stderr)
        return 2
    previous = head_dashboard_hash()
    changed = previous != payload["semantic_hash"]
    print(
        json.dumps(
            {
                "mode": "check",
                "semantic_hash": payload["semantic_hash"],
                "committed_hash": previous,
                "would_change": changed,
                "freshness": payload["freshness"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    site_check = run(sys.executable, "scripts/check_site.py", check=False)
    if site_check.returncode != 0:
        print(site_check.stdout, file=sys.stderr)
        return 2
    print("check: site checks passed")
    return 0


def cmd_refresh(publish: bool) -> int:
    offenders = dirty_outside_generated()
    if offenders:
        print("refresh: refusing: working tree has non-generated changes:", file=sys.stderr)
        for line in offenders:
            print(f"  {line}", file=sys.stderr)
        return 2

    steps = [
        (sys.executable, "-m", "registry", "build"),
        (sys.executable, "-m", "projector", "project"),
        (sys.executable, "scripts/render_registry_page.py"),
        (sys.executable, "scripts/sync_pages_root.py"),
        (sys.executable, "scripts/check_site.py"),
    ]
    for command in steps:
        completed = run(*command, check=False)
        print(completed.stdout, end="")
        if completed.returncode != 0:
            print(completed.stdout, file=sys.stderr)
            print(completed.stderr, file=sys.stderr)
            print(f"refresh: step failed: {' '.join(command)}", file=sys.stderr)
            return 2

    from projector.validate import validate

    payload = json.loads((ROOT / "site" / "dashboard.json").read_text(encoding="utf-8"))[
        "projection"
    ]
    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"refresh: invalid: {error}", file=sys.stderr)
        return 2

    previous = head_dashboard_hash()
    if previous == payload["semantic_hash"]:
        run("git", "checkout", "--", *GENERATED, check=False)
        print(
            json.dumps(
                {
                    "mode": "refresh",
                    "semantic_hash": payload["semantic_hash"],
                    "changed": False,
                    "published": False,
                },
                indent=2,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "mode": "refresh",
                "semantic_hash": payload["semantic_hash"],
                "committed_hash": previous,
                "changed": True,
                "published": False,
            },
            indent=2,
        )
    )
    if not publish:
        print("refresh: working tree updated; re-run with --publish to commit and push")
        return 0

    run("git", "add", "--", *GENERATED)
    staged = run("git", "diff", "--cached", "--name-only")
    if not staged.stdout.strip():
        print("refresh: nothing staged after change detection; not committing")
        return 0
    short = payload["semantic_hash"].split(":")[-1][:12]
    branch = run("git", "branch", "--show-current").stdout.strip()
    run("git", "commit", "-m", f"atlas: dashboard projection {short}")
    pushed = run("git", "push", "origin", branch or "HEAD", check=False)
    if pushed.returncode != 0:
        print(pushed.stdout, file=sys.stderr)
        print(pushed.stderr, file=sys.stderr)
        print("refresh: committed but push failed; merge manually", file=sys.stderr)
        return 2
    print(f"refresh: committed and pushed {branch or 'HEAD'}")
    return 0


def unit_files() -> tuple[Path, Path, Path]:
    unit_dir = ROOT / "systemd" / "user"
    return (
        unit_dir / f"{SERVICE_NAME}.service",
        unit_dir / f"{SERVICE_NAME}.timer",
        Path.home() / ".config" / "systemd" / "user",
    )


def cmd_install_schedule(cadence: str) -> int:
    service_src, timer_src, target_dir = unit_files()
    if not service_src.is_file() or not timer_src.is_file():
        print("schedule: unit files missing from systemd/user", file=sys.stderr)
        return 2
    target_dir.mkdir(parents=True, exist_ok=True)
    timer_text = timer_src.read_text(encoding="utf-8")
    service_text = service_src.read_text(encoding="utf-8").replace("@ATLAS_ROOT@", str(ROOT))
    (target_dir / service_src.name).write_text(service_text, encoding="utf-8")
    (target_dir / timer_src.name).write_text(
        timer_text.replace("OnCalendar=Mon *-*-* 07:13:00", f"OnCalendar={cadence}"),
        encoding="utf-8",
    )
    for command in (
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "--now", f"{SERVICE_NAME}.timer"),
    ):
        completed = subprocess.run(list(command), capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr)
            return 2
    print(f"schedule: installed {SERVICE_NAME}.timer ({cadence}); logs at {LOG_PATH}")
    return 0


def cmd_uninstall_schedule() -> int:
    _, _, target_dir = unit_files()
    subprocess.run(
        ("systemctl", "--user", "disable", "--now", f"{SERVICE_NAME}.timer"),
        capture_output=True,
        check=False,
    )
    for name in (f"{SERVICE_NAME}.service", f"{SERVICE_NAME}.timer"):
        try:
            (target_dir / name).unlink()
        except OSError:
            pass
    subprocess.run(("systemctl", "--user", "daemon-reload"), capture_output=True, check=False)
    print("schedule: uninstalled")
    return 0


def cmd_schedule_status() -> int:
    completed = subprocess.run(
        ("systemctl", "--user", "status", f"{SERVICE_NAME}.timer"),
        capture_output=True,
        text=True,
        check=False,
    )
    print(completed.stdout or completed.stderr)
    if LOG_PATH.is_file():
        print(f"--- {LOG_PATH} (tail) ---")
        print("\n".join(LOG_PATH.read_text(encoding="utf-8").splitlines()[-15:]))
    else:
        print(f"no log yet at {LOG_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas_refresh")
    parser.add_argument("--check", action="store_true", help="dry run: no writes")
    parser.add_argument("--publish", action="store_true", help="commit and push when changed")
    parser.add_argument("--install-schedule", action="store_true")
    parser.add_argument("--uninstall-schedule", action="store_true")
    parser.add_argument("--schedule-status", action="store_true")
    parser.add_argument(
        "--cadence",
        default="Mon *-*-* 07:13:00",
        help="systemd OnCalendar for --install-schedule",
    )
    args = parser.parse_args(argv)

    if args.install_schedule:
        return cmd_install_schedule(args.cadence)
    if args.uninstall_schedule:
        return cmd_uninstall_schedule()
    if args.schedule_status:
        return cmd_schedule_status()
    if args.check:
        return cmd_check()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("refresh: another refresh holds the lock; exiting", file=sys.stderr)
            return 3
        return cmd_refresh(args.publish)


if __name__ == "__main__":
    raise SystemExit(main())
