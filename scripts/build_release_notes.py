#!/usr/bin/env python3
"""Generate structured GitHub Release notes for sudo-skill."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def revision_exists(name: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", name],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def previous_tag(current_tag: str) -> str | None:
    tags = [line.strip() for line in git("tag", "--sort=version:refname").splitlines() if line.strip()]
    if current_tag in tags:
        index = tags.index(current_tag)
        if index > 0:
            return tags[index - 1]
        return None
    return tags[-1] if tags else None


def commit_subjects(current_tag: str, previous: str | None) -> list[str]:
    target = current_tag if revision_exists(current_tag) else "HEAD"
    if previous:
        range_expr = f"{previous}..{target}"
    else:
        range_expr = target
    lines = git("log", range_expr, "--format=%s").splitlines()
    return [line.strip() for line in lines if line.strip()]


def render(tag: str) -> str:
    previous = previous_tag(tag)
    commits = commit_subjects(tag, previous)
    heading = f"# sudo-skill {tag}"
    intro = (
        "Safer `/sudo` workflows for Claude Code with backup before change, diff before rollback, "
        "and object-aware rollback guards for sensitive file edits."
    )
    highlights = [
        "Explicit privileged workflow instead of implicit sandbox-bypass claims",
        "Backups, audit logs, unified diff, and guarded rollback in one installable skill package",
        "GitHub Actions release build that publishes the ready-to-install `sudo-skill.zip` asset",
    ]
    if previous:
        since_line = f"## Changes since `{previous}`"
    else:
        since_line = "## Initial release contents"

    commit_lines = commits or ["Initial project scaffolding"]
    body = [heading, "", intro, "", "## Highlights"]
    body.extend(f"- {item}" for item in highlights)
    body.extend([
        "",
        "## Installation",
        "```bash",
        "mkdir -p ~/.claude/skills",
        "unzip sudo-skill.zip -d /tmp/sudo-skill-release",
        "rm -rf ~/.claude/skills/sudo",
        "mv /tmp/sudo-skill-release/sudo-skill ~/.claude/skills/sudo",
        "```",
        "",
        since_line,
    ])
    body.extend(f"- {item}" for item in commit_lines)
    body.extend([
        "",
        "## Included asset",
        "- `sudo-skill.zip` — installable skill package for Claude Code",
    ])
    return "\n".join(body) + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: build_release_notes.py <tag>", file=sys.stderr)
        return 2
    print(render(sys.argv[1]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
