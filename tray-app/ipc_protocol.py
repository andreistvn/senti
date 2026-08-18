"""
SentiNet — IPC Protocol (shared by daemon and tray).

Defines the message format and socket helpers for communication between the
unprivileged tray process and the root-privileged daemon.  Both sides import
this module, so it must remain free of privilege-specific code.

Protocol
--------
Transport : Unix domain socket (macOS/Linux) or localhost TCP (Windows).
Framing   : One JSON object per line, terminated by ``\\n``.
Direction : The daemon is the *server*; the tray is the *client*.

Message types (daemon → tray):
    STATE_UPDATE      Full snapshot of daemon state (sent every tick).
    TOGGLE_ACK        Confirmation after a toggle request.
    BLACKLIST_UPDATE  A set of MACs that were added/removed from the blacklist.
    EVENT_NEW         A single new detection-log entry.
    HEALTH_UPDATE     Updated daemon service health list.

Message types (tray → daemon):
    TOGGLE_REQUEST    Ask the daemon to flip protection on/off.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

from config import IPC_SOCKET_PATH, IPC_TCP_FALLBACK_PORT

# ── Message types ──────────────────────────────────────────────────────────────

# Daemon → Tray
MSG_STATE_UPDATE = "STATE_UPDATE"
MSG_TOGGLE_ACK = "TOGGLE_ACK"
MSG_BLACKLIST_UPDATE = "BLACKLIST_UPDATE"
MSG_EVENT_NEW = "EVENT_NEW"
MSG_HEALTH_UPDATE = "HEALTH_UPDATE"

# Tray → Daemon
MSG_TOGGLE_REQUEST = "TOGGLE_REQUEST"


def encode(msg_type: str, payload: Dict[str, Any] | None = None) -> bytes:
    """Serialize a message to a newline-terminated JSON bytes line."""
    obj: Dict[str, Any] = {"type": msg_type}
    if payload is not None:
        obj["data"] = payload
    return (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")


def decode(line: str) -> Dict[str, Any]:
    """Deserialize a single JSON line into a message dict."""
    return json.loads(line)


# ── Socket helpers ─────────────────────────────────────────────────────────────

def _use_unix() -> bool:
    """Return True if the platform supports Unix domain sockets."""
    return sys.platform != "win32"


def create_server_socket() -> socket.socket:
    """Create and bind a listening socket (daemon side).

    On Unix  → AF_UNIX socket at IPC_SOCKET_PATH.
    On Win32 → AF_INET TCP socket on 127.0.0.1:IPC_TCP_FALLBACK_PORT.
    """
    if _use_unix():
        # Clean up stale socket file if present.
        if os.path.exists(IPC_SOCKET_PATH):
            os.unlink(IPC_SOCKET_PATH)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(IPC_SOCKET_PATH)
        # Allow read/write for all users so the unprivileged tray can connect
        # even when this socket is created by root.
        os.chmod(IPC_SOCKET_PATH, 0o666)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", IPC_TCP_FALLBACK_PORT))

    sock.listen(4)
    return sock


def create_client_socket() -> socket.socket:
    """Connect to the daemon's IPC socket (tray side).

    Raises ``ConnectionRefusedError`` or ``FileNotFoundError`` if the daemon
    is not running.
    """
    if _use_unix():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(IPC_SOCKET_PATH)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", IPC_TCP_FALLBACK_PORT))
    return sock


def cleanup_server_socket() -> None:
    """Remove the Unix socket file on shutdown."""
    if _use_unix() and os.path.exists(IPC_SOCKET_PATH):
        os.unlink(IPC_SOCKET_PATH)


# ── Buffered line reader ───────────────────────────────────────────────────────

class LineReader:
    """Non-blocking buffered reader that yields complete ``\\n``-terminated
    JSON lines from a streaming socket."""

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._buf = b""

    def read_lines(self) -> List[str]:
        """Read available data and return a list of complete lines.

        Returns an empty list if no complete line is available yet.
        Raises ``ConnectionError`` if the remote end closed.
        """
        try:
            data = self._sock.recv(65536)
        except (BlockingIOError, socket.timeout):
            return []
        if not data:
            raise ConnectionError("remote end closed")

        self._buf += data
        lines: List[str] = []
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                lines.append(text)
        return lines


# ── IPC Server (used by daemon) ────────────────────────────────────────────────

class IpcServer:
    """Accepts tray client connections and broadcasts messages to all clients.

    Usage (in daemon):
        server = IpcServer(on_message=handle_tray_message)
        server.start()
        ...
        server.broadcast(MSG_STATE_UPDATE, state_snapshot)
        ...
        server.stop()
    """

    def __init__(self, on_message: Callable[[str, Dict[str, Any]], None]):
        """
        Parameters
        ----------
        on_message : callable(msg_type, data_dict)
            Called on the accept thread when a tray client sends a message.
        """
        self._on_message = on_message
        self._sock: Optional[socket.socket] = None
        self._clients: List[socket.socket] = []
        self._lock = threading.Lock()
        self._accept_thread: Optional[threading.Thread] = None
        self._client_threads: List[threading.Thread] = []
        self._stop = threading.Event()

    def start(self) -> "IpcServer":
        self._sock = create_server_socket()
        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="ipc-accept"
        )
        self._accept_thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        # Close the server socket to unblock accept().
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        with self._lock:
            for c in self._clients:
                try:
                    c.close()
                except OSError:
                    pass
            self._clients.clear()
        cleanup_server_socket()

    def broadcast(self, msg_type: str, payload: Dict[str, Any] | None = None) -> None:
        """Send a message to every connected tray client."""
        data = encode(msg_type, payload)
        dead: List[socket.socket] = []
        with self._lock:
            for c in self._clients:
                try:
                    c.sendall(data)
                except OSError:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)
                try:
                    c.close()
                except OSError:
                    pass

    # ── internal ──

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()  # type: ignore[union-attr]
            except OSError:
                break
            with self._lock:
                self._clients.append(conn)
            t = threading.Thread(
                target=self._client_loop, args=(conn,), daemon=True, name="ipc-client"
            )
            t.start()
            self._client_threads.append(t)

    def _client_loop(self, conn: socket.socket) -> None:
        reader = LineReader(conn)
        while not self._stop.is_set():
            try:
                lines = reader.read_lines()
            except ConnectionError:
                break
            for line in lines:
                try:
                    msg = decode(line)
                    self._on_message(msg.get("type", ""), msg.get("data", {}))
                except (json.JSONDecodeError, TypeError):
                    pass
        with self._lock:
            if conn in self._clients:
                self._clients.remove(conn)
        try:
            conn.close()
        except OSError:
            pass


# ── IPC Client (used by tray) ─────────────────────────────────────────────────

class IpcClient:
    """Connects to the daemon and dispatches incoming messages to a handler.

    Usage (in tray):
        client = IpcClient(on_message=handle_daemon_message)
        client.start()        # non-blocking, spawns reader thread
        client.send(MSG_TOGGLE_REQUEST)
        ...
        client.stop()
    """

    def __init__(self, on_message: Callable[[str, Dict[str, Any]], None]):
        self._on_message = on_message
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._connected = False
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> "IpcClient":
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ipc-reader"
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def send(self, msg_type: str, payload: Dict[str, Any] | None = None) -> None:
        """Send a message to the daemon.  Silently ignored if disconnected."""
        with self._lock:
            if self._sock and self._connected:
                try:
                    self._sock.sendall(encode(msg_type, payload))
                except OSError:
                    self._connected = False

    # ── internal ──

    def _run(self) -> None:
        """Connect → read loop → reconnect with back-off."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                sock = create_client_socket()
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                self._connected = False
                self._stop.wait(backoff)
                backoff = min(backoff * 1.5, 10.0)
                continue

            with self._lock:
                self._sock = sock
                self._connected = True
            backoff = 1.0

            reader = LineReader(sock)
            while not self._stop.is_set():
                try:
                    lines = reader.read_lines()
                except ConnectionError:
                    break
                for line in lines:
                    try:
                        msg = decode(line)
                        self._on_message(msg.get("type", ""), msg.get("data", {}))
                    except (json.JSONDecodeError, TypeError):
                        pass

            with self._lock:
                self._connected = False
            try:
                sock.close()
            except OSError:
                pass
