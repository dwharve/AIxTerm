"""AIxTerm Client Implementation (socket-only).

Provides connection management, request sending, autostart logic with race
avoidance (lock file) and basic stale socket recovery.
"""

import json
import logging
import os
import platform
import socket
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import AIxTermConfig
from ..runtime_paths import (
    ensure_runtime_layout,
    get_socket_path,
    get_start_lock_path,
    get_config_file,
)

logger = logging.getLogger(__name__)


class AIxTermClient:
    """Client for AIxTerm service (Unix domain socket primary)."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config = AIxTermConfig(Path(config_path) if config_path else None)
        ensure_runtime_layout()
        self.mode = "socket"
        self.socket_path = str(get_socket_path())
        self.connected = False
        self.client_id = str(uuid.uuid4())
        self.connection: Optional[socket.socket] = None

    def connect(self) -> bool:
        if self.connected:
            return True
        return self._connect_socket()

    def _connect_socket(self) -> bool:
        is_windows = platform.system() == "Windows" or not hasattr(socket, "AF_UNIX")
        spath = Path(self.socket_path)

        # Clean up stale non-socket file
        if not is_windows and spath.exists():
            try:
                mode = spath.lstat().st_mode
                if not stat.S_ISSOCK(mode):
                    try:
                        spath.unlink()
                        logger.warning("Removed stale non-socket at socket path: %s", spath)
                    except OSError:
                        pass
            except OSError:
                pass

        if not spath.exists():
            self._ensure_server()

        deadline = time.time() + 2.0
        backoff = 0.05
        restarted = False

        while time.time() < deadline:
            try:
                if is_windows:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    sock.connect(("localhost", 8087))
                    self.connection = sock
                    self.connected = True
                    return True
                # Unix socket path must exist
                if not spath.exists():
                    raise FileNotFoundError(self.socket_path)
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.connect(self.socket_path)
                self.connection = sock
                self.connected = True
                return True
            except FileNotFoundError:
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 0.4)
                continue
            except (ConnectionRefusedError, OSError) as e:
                err_no = getattr(e, "errno", None)
                if not is_windows and err_no in (111, 61):  # 111 Linux, 61 macOS
                    if spath.exists():
                        try:
                            mode = spath.lstat().st_mode
                            if stat.S_ISSOCK(mode):
                                try:
                                    spath.unlink()
                                    logger.warning("Removed stale socket node; restarting service")
                                except OSError:
                                    pass
                        except OSError:
                            pass
                    if not restarted:
                        self._ensure_server()
                        restarted = True
                        time.sleep(backoff)
                        backoff = min(backoff * 1.5, 0.4)
                        continue
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 0.4)
                continue
            except Exception as e:  # unexpected
                logger.error("Unexpected error during connect: %s", e)
                break

        if not spath.exists():
            logger.error("Socket file not present after attempts: %s", self.socket_path)
        else:
            logger.error("Failed to connect to AIxTerm service within timeout window")
        self.connected = False
        self.connection = None
        return False

    def disconnect(self):
        if not self.connected:
            return
        if self.connection:
            try:
                self.connection.close()
            except Exception as e:
                logger.error("Error disconnecting: %s", e)
        self.connected = False
        self.connection = None

    def query(self, question: str, **options) -> Dict[str, Any]:
        request = {
            "id": str(uuid.uuid4()),
            "type": "query",
            "timestamp": self._get_timestamp(),
            "payload": {"question": question, "options": options},
        }
        return self.send_request(request)

    def status(self) -> Dict[str, Any]:
        request = {
            "id": str(uuid.uuid4()),
            "type": "status",
            "timestamp": self._get_timestamp(),
        }
        return self.send_request(request)

    def control(self, command: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if data is None:
            data = {}
        request = {
            "id": str(uuid.uuid4()),
            "type": "control",
            "timestamp": self._get_timestamp(),
            "payload": {"command": command, "data": data},
        }
        return self.send_request(request)

    def plugin_request(self, plugin_id: str, command: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if data is None:
            data = {}
        request = {
            "id": str(uuid.uuid4()),
            "type": "plugin",
            "timestamp": self._get_timestamp(),
            "payload": {"plugin_id": plugin_id, "command": command, "data": data},
        }
        return self.send_request(request)

    def send_request(self, request: Dict) -> Dict[str, Any]:
        if not self.connected and not self.connect():
            return {
                "status": "error",
                "error": {"code": "connection_error", "message": "Could not connect to AIxTerm service"},
            }
        return self._send_socket_request(request)

    def _send_socket_request(self, request: Dict) -> Dict[str, Any]:
        try:
            request_data = json.dumps(request).encode("utf-8") + b"\n"
            if not self.connection:
                return {"status": "error", "error": {"code": "not_connected", "message": "Not connected"}}
            # Temporarily increase timeout for request/response to accommodate LLM latency
            old_timeout = None
            try:
                old_timeout = self.connection.gettimeout()
            except Exception:
                pass
            try:
                self.connection.settimeout(60.0)
            except Exception:
                pass
            try:
                self.connection.sendall(request_data)
                # If this is a streaming query, consume event stream
                is_streaming = (
                    request.get("type") == "query"
                    and isinstance(request.get("payload"), dict)
                    and isinstance(request["payload"].get("options"), dict)
                    and bool(request["payload"]["options"].get("stream"))
                )
                if is_streaming:
                    buffer = b""
                    final_result: Dict[str, Any] = {}
                    while True:
                        chunk = self.connection.recv(4096)
                        if not chunk:
                            break
                        buffer += chunk
                        while b"\n" in buffer:
                            line, _, buffer = buffer.partition(b"\n")
                            if not line:
                                continue
                            try:
                                evt = json.loads(line.decode("utf-8"))
                            except Exception:
                                continue
                            event_type = evt.get("event")
                            if event_type == "stream_start":
                                continue
                            if event_type == "stream_chunk":
                                text = evt.get("text", "")
                                if text:
                                    # print chunk live
                                    print(text, end="", flush=True)
                                continue
                            if event_type == "stream_end":
                                final_result = evt.get("result", {}) or {}
                                # ensure newline after stream
                                print()
                                return {"status": "success", "result": final_result, "already_streamed": True}
                            # Fallback: if we got a non-event success, return it
                            if evt.get("status") in ("success", "error") and not event_type:
                                return evt
                    # If stream ended unexpectedly
                    return {"status": "error", "error": {"code": "stream_ended", "message": "Connection closed during stream"}}
                else:
                    response_data = b""
                    while True:
                        chunk = self.connection.recv(4096)
                        if not chunk:
                            break
                        response_data += chunk
                        if b"\n" in response_data:
                            break
                    response_text = response_data.decode("utf-8")
                    return json.loads(response_text)
            finally:
                try:
                    # Restore original timeout
                    self.connection.settimeout(old_timeout)
                except Exception:
                    pass
        except Exception as e:
            logger.error("Error sending request: %s", e)
            self.connected = False
            self.connection = None
            return {"status": "error", "error": {"code": "communication_error", "message": str(e)}}

    def _get_timestamp(self) -> str:
        import datetime
        return datetime.datetime.now().isoformat()

    # -------- Full process restart utilities --------
    def _find_service_pids(self) -> list[int]:
        """Best-effort find running AIxTerm service PIDs.

        We search process command lines for the module invocation
        "-m aixterm.service.service". This is scoped to the current user.
        """
        pids: list[int] = []
        try:
            import subprocess
            # Limit to current user for safety
            cmd = "ps -u $(id -u) -o pid=,args="
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                try:
                    pid_str, args = line.strip().split(maxsplit=1)
                    if "-m aixterm.service.service" in args:
                        pids.append(int(pid_str))
                except Exception:
                    continue
        except Exception:
            pass
        return pids

    def _terminate_pids(self, pids: list[int], timeout: float = 2.0) -> None:
        """Terminate PIDs with SIGTERM, escalate to SIGKILL after timeout."""
        import signal
        import time as _time
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            except Exception:
                continue
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            alive = [pid for pid in pids if self._pid_exists(pid)]
            if not alive:
                break
            _time.sleep(0.05)
        # Escalate remaining
        for pid in [pid for pid in pids if self._pid_exists(pid)]:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

    def _pid_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except Exception:
            return True

    def full_restart(self) -> Dict[str, Any]:
        """Perform a complete service restart by stopping the process and spawning a new one."""
        import platform as _platform
        # On Windows fallback to control-restart
        if _platform.system() == "Windows":
            return self.control("restart")

        # Terminate existing service processes
        pids = self._find_service_pids()
        if pids:
            self._terminate_pids(pids)
        # Wait for socket node to disappear
        try:
            spath = Path(self.socket_path)
            deadline = time.time() + 2.0
            while time.time() < deadline and spath.exists():
                time.sleep(0.05)
        except Exception:
            pass

        # Start new service process
        try:
            self._ensure_server()
            # Attempt connection
            if self.connect():
                return {"status": "success", "result": {"message": "Service fully restarted"}}
            return {"status": "error", "error": {"code": "restart_failed", "message": "Service did not start"}}
        except Exception as e:
            return {"status": "error", "error": {"code": "restart_failed", "message": str(e)}}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _ensure_server(self) -> None:
        socket_path = Path(self.socket_path)
        if socket_path.exists():
            return
        lock_path = get_start_lock_path()
        started_by_us = False
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            started_by_us = True
        except FileExistsError:
            pass
        if started_by_us:
            cmd = [
                sys.executable,
                "-m",
                "aixterm.service.service",
                "--config",
                str(get_config_file()),
            ]
            try:
                # Propagate minimal environment; ensure pytest marker retained if present so
                # idle shutdown monitor activates under tests. Some CI or isolated test
                # environments may not automatically propagate PYTEST_CURRENT_TEST to the
                # spawned detached process; we forward it explicitly if set.
                env = os.environ.copy()
                for var in (
                    "PYTEST_CURRENT_TEST",
                    "AIXTERM_TEST_IDLE_LIMIT",
                    "AIXTERM_TEST_IDLE_GRACE",
                    "AIXTERM_RUNTIME_HOME",
                ):
                    if var in os.environ:
                        env[var] = os.environ[var]
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    env=env,
                )
            except Exception as e:
                logger.error("Failed to spawn service: %s", e)
        deadline = time.time() + 2.0
        delay = 0.05
        while time.time() < deadline:
            if socket_path.exists():
                break
            time.sleep(delay)
            delay = min(delay * 1.5, 0.5)
        if started_by_us and lock_path.exists():
            try:
                os.unlink(lock_path)
            except OSError:
                pass
