import time
from aixterm.client.client import AIxTermClient
from aixterm.runtime_paths import get_socket_path


def test_service_autostarts_and_persists(monkeypatch, tmp_path):
    """AIxTerm service should autostart on first client connect and persist for subsequent requests.

    This test asserts core service lifecycle behavior (socket presence + service uptime monotonicity)
    without depending on MCP server internals. MCP server availability is intentionally treated as
    an implementation detail: if configured servers start they will show up in status, but the
    contract under test is that the AIxTerm service process remains alive between client requests.
    """
    # Isolate runtime
    monkeypatch.setenv("AIXTERM_RUNTIME_HOME", str(tmp_path))
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "service-autostart-persistence")
    # Provide a generous idle window so background idle monitor (test mode) won't kill service mid‑test
    monkeypatch.setenv("AIXTERM_TEST_IDLE_LIMIT", "5.0")

    sock_path = get_socket_path()
    if sock_path.exists():
        try:  # Defensive cleanup
            sock_path.unlink()
        except OSError:
            pass

    client = AIxTermClient()
    # First connect should autostart service
    assert client.connect() is True, "Client failed to connect (autostart)"
    # Give the service a brief moment to finish initializing before polling status
    time.sleep(0.05)
    assert sock_path.exists(), "Socket not created by autostarted service"

    # Capture initial status; allow brief retries because service may still be initializing
    first_status = None
    for _ in range(40):  # expanded retry loop while service initializes
        resp = client.status()
        if resp.get("status") == "success" and resp.get("result"):
            svc = resp["result"]
            if svc.get("running") and svc.get("uptime") is not None:
                first_status = svc
                break
        time.sleep(0.05)
    assert first_status, "Did not obtain initial running service status"
    first_uptime = first_status.get("uptime")
    assert isinstance(first_uptime, (int, float)) and first_uptime >= 0

    # Issue additional requests separated by delays; uptime should increase monotonically
    time.sleep(0.3)
    resp2 = client.status()
    assert resp2.get("status") == "success"
    svc2 = resp2.get("result", {})
    assert svc2.get("running") is True
    second_uptime = svc2.get("uptime")
    assert isinstance(second_uptime, (int, float)) and second_uptime >= first_uptime

    # Disconnect client; service should remain up and socket should still exist (no idle shutdown yet)
    client.disconnect()
    assert sock_path.exists(), "Socket disappeared immediately after client disconnect"

    # Reconnect new client and ensure uptime continues (not restarted)
    client2 = AIxTermClient()
    assert client2.connect() is True
    resp3 = client2.status()
    assert resp3.get("status") == "success"
    svc3 = resp3.get("result", {})
    assert svc3.get("running") is True
    third_uptime = svc3.get("uptime")
    assert isinstance(third_uptime, (int, float)) and third_uptime >= second_uptime

    # Ensure we didn't restart (uptime shouldn't reset to a tiny number)
    assert third_uptime - first_uptime < 10.0
