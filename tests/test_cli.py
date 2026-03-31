from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def cli_env(tmp_path):
    env = os.environ.copy()
    env["SUDO_SKILL_HOME"] = str(tmp_path / "skill-home")
    return env


def run_cli(*args, env):
    return subprocess.run(
        [sys.executable, str(ROOT / "sudo.py"), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_integration_flow(cli_env, tmp_path):
    target = tmp_path / "tracked.txt"
    target.write_text("before\n", encoding="utf-8")

    result = run_cli("enter", env=cli_env)
    assert result.returncode == 0
    assert "Entered /sudo explicit privileged workflow" in result.stdout

    result = run_cli("log-modify", str(target), env=cli_env)
    assert result.returncode == 0
    target.write_text("after\n", encoding="utf-8")

    result = run_cli("finalize-modify", str(target), env=cli_env)
    assert result.returncode == 0

    result = run_cli("history", "5", env=cli_env)
    assert result.returncode == 0
    assert "modify" in result.stdout

    result = run_cli("diff", str(target), env=cli_env)
    assert result.returncode == 0
    assert "before:" in result.stdout
    assert "after" in result.stdout

    result = run_cli("rollback", "1", "--yes", env=cli_env)
    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == "before\n"

    result = run_cli("exit", env=cli_env)
    assert result.returncode == 0
    assert "Exited /sudo workflow" in result.stdout


def test_release_zip_is_clean(cli_env):
    dist = ROOT / "dist"
    if dist.exists():
        for item in dist.iterdir():
            if item.is_file():
                item.unlink()

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_release.py")],
        cwd=ROOT,
        env=cli_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    zip_path = dist / "sudo-skill.zip"
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert all("__MACOSX" not in name for name in names)
    assert "sudo-skill/SKILL.md" in names
    assert "sudo-skill/README.en.md" in names
    assert "sudo-skill/CHANGELOG.md" in names
    assert "sudo-skill/SECURITY.md" in names
    assert "sudo-skill/SUPPORT.md" in names
    assert "sudo-skill/tests/test_cli.py" not in names


def test_release_notes_can_be_generated_before_tag_exists(cli_env):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_release_notes.py"), "v9999.99.99-preview"],
        cwd=ROOT,
        env=cli_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "# sudo-skill v9999.99.99-preview" in result.stdout
    assert "## 这个版本适合谁" in result.stdout
