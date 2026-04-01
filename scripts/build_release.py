#!/usr/bin/env python3
"""Build a clean, installable sudo skill release zip."""

from __future__ import annotations

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ZIP_PATH = DIST / "sudo-skill.zip"
INCLUDE_PATHS = [
    "SKILL.md",
    "sudo.py",
    "operation_logger.py",
    "README.md",
    "README.en.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "SUPPORT.md",
    "LICENSE",
    "references/state-tracking.md",
]


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in INCLUDE_PATHS:
            source = ROOT / relative
            archive.write(source, f"sudo-skill/{relative}")

    print(f"Built {ZIP_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
