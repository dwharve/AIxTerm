import time
from aixterm.client.client import AIxTermClient
from aixterm.runtime_paths import get_socket_path


def test_service_idle_auto_shutdown(monkeypatch, tmp_path):
    """Service started via autostart should terminate after configured idle limit."""
    monkeypatch.setenv("AIXTERM_RUNTIME_HOME", str(tmp_path))
    monkeypatch.setenv("AIXTERM_TEST_IDLE_LIMIT", "0.3")  # 300ms idle
    monkeypatch.setenv("AIXTERM_TEST_IDLE_GRACE", "0.4")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "idle-shutdown-test")

    client = AIxTermClient()
    for _ in range(10):
        if client.connect():
            break
        time.sleep(0.05)
    assert client.connected is True
    client.status()
    sock = get_socket_path()
    assert sock.exists()
    time.sleep(0.9)  # > grace + idle
    assert not sock.exists(), "Service socket still present after idle shutdown window"
    client2 = AIxTermClient()
    assert client2.connect() is True
    # Just confirming socket recreated; no need to store unused variable
    assert get_socket_path().exists()
