from __future__ import annotations

import os
from pathlib import Path

import pytest

from operation_logger import OperationLogger, snapshot_path


@pytest.fixture()
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUDO_SKILL_HOME", str(tmp_path / "skill-home"))
    return Path(os.environ["SUDO_SKILL_HOME"])


def test_small_modify_backup_and_diff(isolated_home, tmp_path):
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello\nworld\n", encoding="utf-8")

    logger = OperationLogger()
    op_id = logger.log_modify(file_path)
    file_path.write_text("hello\nClaude\n", encoding="utf-8")
    logger.finalize_modify(file_path, op_id)

    diff = logger.build_diff_report(str(file_path))
    assert "-world" in diff
    assert "+Claude" in diff


def test_large_modify_branch_records_backup_without_hashlib_error(isolated_home, tmp_path):
    file_path = tmp_path / "large.bin"
    file_path.write_bytes(b"a" * (1024 * 1024 + 8))

    logger = OperationLogger()
    op_id = logger.log_modify(file_path)
    file_path.write_bytes(b"b" * (1024 * 1024 + 8))
    logger.finalize_modify(file_path, op_id)

    operation = logger.operations[-1]
    assert operation["backup"]["storage"] == "gzip-original"
    assert Path(operation["backup"]["backup_path"]).exists()


def test_delete_rollback_restores_file(isolated_home, tmp_path):
    file_path = tmp_path / "delete-me.txt"
    file_path.write_text("remove me", encoding="utf-8")

    logger = OperationLogger()
    logger.log_delete(file_path)
    file_path.unlink()

    ok, _ = logger.rollback(1)
    assert ok is True
    assert file_path.read_text(encoding="utf-8") == "remove me"


def test_create_rollback_refuses_if_file_changed(isolated_home, tmp_path):
    file_path = tmp_path / "new.txt"
    file_path.write_text("v1", encoding="utf-8")

    logger = OperationLogger()
    logger.log_create(file_path)
    file_path.write_text("v2", encoding="utf-8")

    ok, messages = logger.rollback(1)
    assert ok is False
    assert any("Refusing to remove a changed file" in message for message in messages)
    assert file_path.read_text(encoding="utf-8") == "v2"


def test_move_and_chmod_rollback(isolated_home, tmp_path):
    src = tmp_path / "from.txt"
    dst = tmp_path / "to.txt"
    src.write_text("moved", encoding="utf-8")

    src.rename(dst)
    logger = OperationLogger()
    logger.log_move(src, dst)
    ok, messages = logger.rollback(1)
    assert ok is True
    assert src.exists() and not dst.exists()
    assert any("Rolled back move" in message for message in messages)

    chmod_target = tmp_path / "chmod.txt"
    chmod_target.write_text("mode", encoding="utf-8")
    old_mode = chmod_target.stat().st_mode
    chmod_target.chmod(0o600)
    logger = OperationLogger()
    logger.log_chmod(chmod_target, old_mode, 0o600)
    ok, messages = logger.rollback(1)
    assert ok is True
    assert any("Rolled back chmod" in message for message in messages)


def test_repeated_rollback_does_not_reapply_same_operation(isolated_home, tmp_path):
    file_path = tmp_path / "repeat.txt"
    file_path.write_text("one", encoding="utf-8")

    logger = OperationLogger()
    logger.log_delete(file_path)
    file_path.unlink()
    first_ok, _ = logger.rollback(1)
    second_ok, messages = logger.rollback(1)

    assert first_ok is True
    assert second_ok is False
    assert any("cannot rollback" in message.lower() or "only found 0 active" in message.lower() for message in messages)


def test_clean_old_backup_directory(isolated_home):
    logger = OperationLogger()
    old_dir = logger.backup_dir / "2000-01-01"
    old_dir.mkdir(parents=True)
    (old_dir / "old.gz").write_text("old", encoding="utf-8")

    from sudo import clean_old_backups

    clean_old_backups(7)
    assert not old_dir.exists()


def test_binary_diff_returns_summary(isolated_home, tmp_path):
    file_path = tmp_path / "image.bin"
    file_path.write_bytes(b"\0\x01before")

    logger = OperationLogger()
    op_id = logger.log_modify(file_path)
    file_path.write_bytes(b"\0\x02after")
    logger.finalize_modify(file_path, op_id)

    report = logger.build_diff_report(str(file_path))
    assert "Binary file summary" in report
    assert "current_hash" in report
