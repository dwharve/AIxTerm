"""Tests for TTY log processing with new ~/.aixterm/tty layout (no legacy)."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aixterm.config import AIxTermConfig
from aixterm.context.log_processor import LogProcessor


@pytest.fixture
def config():
    return AIxTermConfig()


@pytest.fixture
def log_processor(config):
    return LogProcessor(config, Mock())


@pytest.fixture
def mock_home_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        home_path = Path(temp_dir)
        with patch("pathlib.Path.home", return_value=home_path):
            yield home_path


def _make_logs(home: Path, names):
    log_dir = home / ".aixterm" / "tty"
    log_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for n, content in names:
        p = log_dir / f"{n}.log"
        p.write_text(content)
        paths.append(p)
    return log_dir, paths


def test_get_current_tty_detection(log_processor):
    if not hasattr(os, "ttyname"):
        assert log_processor._get_current_tty() is None
        return
    with patch("os.ttyname", side_effect=OSError("Not a tty")):
        with patch("sys.stdin.fileno", side_effect=OSError("No fileno")):
            assert log_processor._get_current_tty() is None
    with patch("os.ttyname", return_value="/dev/pts/7"):
        with patch("sys.stdin.fileno", return_value=0):
            assert log_processor._get_current_tty() == "pts-7"


def test_validate_log_tty_match(log_processor, mock_home_dir):
    log_dir, (pts1, pts2, default) = _make_logs(
        mock_home_dir,
        [
            ("pts-1", "current"),
            ("pts-2", "other"),
            ("default", "default"),
        ],
    )
    with patch.object(log_processor, "_get_current_tty", return_value="pts-1"):
        assert log_processor.validate_log_tty_match(pts1) is True
        assert log_processor.validate_log_tty_match(pts2) is False
        assert log_processor.validate_log_tty_match(default) is False
    with patch.object(log_processor, "_get_current_tty", return_value=None):
        # Only default should match when no TTY
        assert log_processor.validate_log_tty_match(default) is True
        assert log_processor.validate_log_tty_match(pts1) is False


def test_get_log_files_filtered(log_processor, mock_home_dir):
    log_dir, (pts1, pts2, default) = _make_logs(
        mock_home_dir,
        [
            ("pts-1", "a"),
            ("pts-2", "b"),
            ("default", "c"),
        ],
    )
    with patch.object(log_processor, "_get_current_tty", return_value="pts-1"):
        files = log_processor.get_log_files()
        assert files == [pts1]
    with patch.object(log_processor, "_get_current_tty", return_value=None):
        files = log_processor.get_log_files()
        # Only default returned when no TTY
        assert files == [default]
    # All logs when not filtering
    with patch.object(log_processor, "_get_current_tty", return_value="pts-1"):
        files = log_processor.get_log_files(filter_tty=False)
        assert set(files) == {pts1, pts2, default}


def test_find_log_file(log_processor, mock_home_dir):
    log_dir, (pts_target, _, _) = _make_logs(
        mock_home_dir, [("pts-3", "x"), ("default", "d"), ("pts-2", "y")]
    )
    with patch.object(log_processor, "_get_current_tty", return_value="pts-3"):
        found = log_processor.find_log_file()
        assert found == pts_target


def test_log_entry_creation(log_processor, mock_home_dir):
    with patch.object(log_processor, "_get_current_tty", return_value="pts-9"):
        log_processor.create_log_entry("echo hi", "hi")
        log_path = mock_home_dir / ".aixterm" / "tty" / "pts-9.log"
        assert log_path.exists()
        content = log_path.read_text()
        assert "$ echo hi" in content
        assert "hi" in content


def test_isolation_between_sessions(log_processor, mock_home_dir):
    sessions = {
        "pts-1": [("ls", "files"), ("pwd", "/tmp")],
        "pts-2": [("git status", "On branch"), ("whoami", "user")],
    }
    for tty, cmds in sessions.items():
        with patch.object(log_processor, "_get_current_tty", return_value=tty):
            for c, o in cmds:
                log_processor.create_log_entry(c, o)
    for tty, cmds in sessions.items():
        with patch.object(log_processor, "_get_current_tty", return_value=tty):
            lf = log_processor.find_log_file()
            text = lf.read_text()
            for c, o in cmds:
                assert c in text and o in text
            for other_tty, other_cmds in sessions.items():
                if other_tty != tty:
                    for c, o in other_cmds:
                        assert c not in text


def test_performance_many_logs(log_processor, mock_home_dir):
    # Create many logs and ensure filtering remains O(1) for current tty
    names = [(f"pts-{i}", "x") for i in range(120)]
    _make_logs(mock_home_dir, names)
    with patch.object(log_processor, "_get_current_tty", return_value="pts-50"):
        files = log_processor.get_log_files()
        assert len(files) == 1
        assert files[0].name == "pts-50.log"
