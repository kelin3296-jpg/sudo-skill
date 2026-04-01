#!/usr/bin/env python3
"""Generate Chinese-first GitHub Release notes for sudo-skill."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"


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


def changelog_section(tag: str) -> str | None:
    version = tag[1:] if tag.startswith("v") else tag
    text = CHANGELOG.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    lines = match.group(0).splitlines()[1:]
    return "\n".join(lines).strip()


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
    changelog = changelog_section(tag)
    commits = commit_subjects(tag, previous)
    body = [
        f"# sudo-skill {tag}",
        "",
        "面向 Claude Code 的安全 `/sudo` 工作流：先备份、再修改；先看 diff、再回滚；用日志和快照把高风险修改的后顾之忧降下来。",
        "",
        "## 这个版本适合谁",
        "- 想在 Claude Code 里处理敏感文件、系统路径或高风险修改的用户",
        "- 希望在进入 `/sudo` 风格流程前，就先有回退方案的用户",
        "- 想把“日志 + 备份 + 回滚”当成兜底路径，而不是事后猜测如何恢复的用户",
        "",
        "## 安装",
        "```bash",
        "mkdir -p ~/.claude/skills",
        "unzip sudo-skill.zip -d /tmp/sudo-skill-release",
        "rm -rf ~/.claude/skills/sudo",
        "mv /tmp/sudo-skill-release/sudo-skill ~/.claude/skills/sudo",
        "```",
        "",
        "## 本版更新",
    ]
    if changelog:
        body.append(changelog)
    else:
        commit_lines = commits or ["首次版本发布"]
        body.extend(f"- {item}" for item in commit_lines)
    body.extend([
        "",
        "## 附带资源",
        "- `sudo-skill.zip`：可直接安装到 Claude Code 的 skill 压缩包",
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
