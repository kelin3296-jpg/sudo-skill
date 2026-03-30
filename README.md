# sudo-skill

[![CI](https://github.com/kelin3296-jpg/sudo-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/kelin3296-jpg/sudo-skill/actions/workflows/ci.yml)
![Claude Code](https://img.shields.io/badge/runtime-Claude%20Code-5b5bd6)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![License](https://img.shields.io/badge/license-MIT-green)

Safer `/sudo` workflows for Claude Code — backup before change, diff before rollback, and object-aware rollback guards for sensitive file edits.

中文说明见 [`README.zh-CN.md`](README.zh-CN.md).

## Why this exists

Claude Code users often need a lightweight `/sudo` mental model for high-risk edits, but "auto-elevated mode" is both misleading and unsafe. `sudo-skill` keeps the command shape familiar while making the contract explicit:

- enter an explicit privileged workflow
- back up files before changing them
- inspect text diffs before rollback
- refuse destructive rollback when the tracked file object has changed
- keep an audit trail that stays understandable after rollback

## At a glance

- **Runtime**: Claude Code only
- **Scope**: explicit privileged workflow, not automatic sandbox bypass
- **Core features**: backup, audit log, unified diff, guarded rollback, release zip packaging
- **Storage**: `~/.claude` by default, or `SUDO_SKILL_HOME` for isolated environments

## Quick start

```bash
python sudo.py enter
python sudo.py log-modify ~/.ssh/config
# edit the file
python sudo.py finalize-modify ~/.ssh/config
python sudo.py diff ~/.ssh/config
python sudo.py rollback 1 --yes
python sudo.py exit
```

## Install

Install from a local working tree:

```bash
mkdir -p ~/.claude/skills
cp -R ./sudo-skill ~/.claude/skills/sudo
```

Install from the release zip:

```bash
mkdir -p ~/.claude/skills
unzip dist/sudo-skill.zip -d /tmp/sudo-skill-release
rm -rf ~/.claude/skills/sudo
mv /tmp/sudo-skill-release/sudo-skill ~/.claude/skills/sudo
```

## Public commands

```bash
python sudo.py enter
python sudo.py exit
python sudo.py status
python sudo.py clean --days 7
python sudo.py purge --yes
python sudo.py history 20
python sudo.py rollback 1 --yes
python sudo.py diff [path|history-index]
```

## Integrator commands used by the skill

These commands keep `operation_logger.py` internal while still letting the skill track changes via the public CLI:

```bash
python sudo.py log-modify <path>
python sudo.py finalize-modify <path> [--id OP_ID]
python sudo.py log-delete <path>
python sudo.py log-create <path>
python sudo.py log-move <src> <dst>
python sudo.py log-chmod <path> <old_mode_octal> <new_mode_octal>
```

## Storage

By default the skill stores state under `~/.claude`:

- `~/.claude/sudo-backups/`
- `~/.claude/sudo-logs/`
- `~/.claude/sudo-state.json`

Set `SUDO_SKILL_HOME` to isolate development, testing, or custom installations.

## Safety notes

- The skill does **not** automatically elevate Claude Code commands.
- Rollback refuses destructive actions if the tracked file object no longer matches the recorded snapshot.
- `delete` rollback refuses to overwrite a path that has been reused.
- `create` rollback refuses to delete a file that changed after creation.

## Demo walkthrough

```text
$ python sudo.py enter
Entered /sudo explicit privileged workflow.

$ python sudo.py log-modify ~/.ssh/config
Recorded modify operation #1 for /Users/you/.ssh/config

$ python sudo.py finalize-modify ~/.ssh/config
Finalized modify operation #1 for /Users/you/.ssh/config

$ python sudo.py diff ~/.ssh/config
--- before:/Users/you/.ssh/config
+++ current:/Users/you/.ssh/config
@@ ...

$ python sudo.py rollback 1 --yes
Rolled back modify: /Users/you/.ssh/config

$ python sudo.py exit
Exited /sudo workflow.
```

## Development

```bash
python3 -m venv .venv
./.venv/bin/pip install pytest
./.venv/bin/python -m pytest
python3 scripts/build_release.py
```

The release builder creates `dist/sudo-skill.zip` without `__MACOSX`, tests, or cache files.

Tags like `v0.1.0` trigger `.github/workflows/release.yml` to run tests, build the zip, and publish a GitHub Release with structured notes.

If you publish this repository under a different GitHub owner or repo name, update the badge URLs at the top of this file.
