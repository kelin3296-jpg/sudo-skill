# sudo-skill

[![CI](https://github.com/kelin3296-jpg/sudo-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/kelin3296-jpg/sudo-skill/actions/workflows/ci.yml)
![Claude Code](https://img.shields.io/badge/runtime-Claude%20Code-5b5bd6)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![License](https://img.shields.io/badge/license-MIT-green)

English companion for a Chinese-first repository. The main README now lives in [`README.md`](README.md).

`sudo-skill` gives Claude Code users a safer `/sudo` workflow with backup before change, diff before rollback, and logged recovery paths when sensitive edits feel risky.

## Why it exists

The hard part of privileged edits is usually not the command itself. It is the fear of being stuck after a bad change. This project reduces that hesitation by turning `/sudo` into an explicit, auditable, reversible workflow.

## What it provides

- backup before change
- diff before rollback
- guarded rollback when object identity no longer matches
- logs and snapshots as the fallback path

## Fast install prompt for Claude Code

```text
Please install `sudo-skill` from this GitHub repository:
https://github.com/kelin3296-jpg/sudo-skill

Requirements:
1. Download the latest GitHub Release asset named `sudo-skill.zip`
2. Install it to `~/.claude/skills/sudo`
3. Back up the existing directory first if `~/.claude/skills/sudo` already exists
4. Run `python3 ~/.claude/skills/sudo/sudo.py status` after installation
5. Explain how to use `/sudo`, `/sudo diff`, `/sudo history 5`, and `/sudo rollback 1 --yes`
6. If the release asset is unavailable, fall back to installing from repository contents and say which path you used
```

For full Chinese documentation, changelog, support, and contribution docs, start from [`README.md`](README.md).
