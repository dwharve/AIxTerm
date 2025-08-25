import os
import stat
import threading
import time
from pathlib import Path

import pytest

from aixterm.runtime_paths import (
    ensure_runtime_layout,
    get_runtime_dir,
    get_socket_path,
    get_start_lock_path,
)
from aixterm.client.client import AIxTermClient


@pytest.fixture()
def temp_home(monkeypatch, tmp_path):
    """Provide an isolated HOME directory and patch Path.home()."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    return tmp_path


def _is_socket(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    return stat.S_ISSOCK(mode)


def test_ensure_runtime_layout_creates_secure_dir(temp_home):
    runtime_dir = ensure_runtime_layout()
    assert runtime_dir == temp_home / ".aixterm"
    assert runtime_dir.exists()
    perms = stat.S_IMODE(runtime_dir.stat().st_mode)
    # Expect 0700 permissions (strict)
    assert perms & 0o777 == 0o700


def test_runtime_dir_functions_ignore_start_param(temp_home):
    # Pass an arbitrary start path and ensure runtime dir still fixed at HOME
    arbitrary = temp_home / "some" / "nested" / "dir"
    arbitrary.mkdir(parents=True)
    runtime_dir = get_runtime_dir(start=arbitrary)
    assert runtime_dir == temp_home / ".aixterm"
    # ensure config/socket paths derive from same runtime
    assert get_socket_path().parent == runtime_dir


def test_client_autostart_creates_socket(temp_home):
    # Precondition: no socket
    socket_path = get_socket_path()
    assert not socket_path.exists()
    client = AIxTermClient()
    connected = client.connect()
    assert connected is True
    assert socket_path.exists()
    assert _is_socket(socket_path) or os.name == "nt"  # Windows may use TCP fallback
    # Lock file should not persist
    assert not get_start_lock_path().exists()


def test_stale_socket_recovery(temp_home):
    # Create runtime dir and a stale regular file where socket should be
    rd = ensure_runtime_layout()
    stale = get_socket_path()
    rd.mkdir(exist_ok=True, parents=True)
    stale.write_text("stale")
    assert stale.exists() and not _is_socket(stale)
    client = AIxTermClient()
    assert client.connect() is True
    # After connect, socket path should be a real socket (or TCP used on Windows)
    if os.name != "nt":
        assert _is_socket(stale)
    # Basic status request sanity
    # We only verify the stale socket was replaced; higher-level protocol tests exist elsewhere.


def test_lock_race_simulation(temp_home):
    # Spawn two clients concurrently to simulate race
    results = []

    def connect_client():
        c = AIxTermClient()
        results.append(c.connect())

    t1 = threading.Thread(target=connect_client)
    t2 = threading.Thread(target=connect_client)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert any(results)  # At least one succeeded
    # Socket present
    sp = get_socket_path()
    assert sp.exists()
    # Lock should be cleared (allow brief delay for cleanup)
    for _ in range(10):
        if not get_start_lock_path().exists():
            break
        time.sleep(0.05)
    assert not get_start_lock_path().exists()
