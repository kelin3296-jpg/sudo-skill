#!/usr/bin/env python3
"""Hook script for Claude Code to check sudo state and auto-allow permissions."""

import json
import sys
from pathlib import Path


def get_sudo_state() -> dict:
    """Check if sudo mode is active by reading sudo-state.json."""
    # Try to resolve the state file location (same logic as sudo.py)
    skill_home = Path.home() / ".claude"
    state_file = skill_home / "sudo-state.json"

    if not state_file.exists():
        return {"active": False}

    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {"active": False}


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        input_data = {}

    state = get_sudo_state()
    sudo_active = state.get("active", False)

    if sudo_active:
        # Sudo is active - auto-allow this tool call
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "/sudo mode is active - auto-allowed"
            },
            "systemMessage": "/sudo active: auto-allowed"
        }
    else:
        # Sudo not active - let normal permission flow continue
        output = {
            "continue": True
        }

    # Output JSON for Claude Code
    json.dump(output, sys.stdout, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
