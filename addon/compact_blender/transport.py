"""Bounded, loopback-only JSON transport, polled by Blender's main-thread timer.

No background thread calls bpy. One JSON line per connection; no implicit retries.
"""

import hashlib
import hmac
import json
import os
import secrets
import socket
import time
from collections import OrderedDict
from pathlib import Path

MAX_REQUEST = 262144
MAX_CLIENTS = 8


def state_dir():
    base = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("XDG_STATE_HOME")
        or str(Path.home() / ".local/state")
    )
    return Path(base) / "blender-compact-mcp"


def encode(value):
    return (json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


class Server:
    def __init__(self, engine, descriptor=None):
        self.engine = engine
        self.token = secrets.token_urlsafe(32)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(MAX_CLIENTS)
        self.socket.setblocking(False)
        self.clients = {}
        self.cache = OrderedDict()
        self.closed = False
        self.descriptor = Path(descriptor) if descriptor else state_dir() / f"connection-{os.getpid()}.json"
        self.descriptor.parent.mkdir(parents=True, exist_ok=True)
        self.engine.output_dir.mkdir(parents=True, exist_ok=True)
        info = {
            "protocol": 1,
            "host": "127.0.0.1",
            "port": self.socket.getsockname()[1],
            "token": self.token,
            "pid": os.getpid(),
            "output_dir": str(self.engine.output_dir.resolve()),
        }
        fd = os.open(self.descriptor, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(info, out)

    def handle(self, request):
        if not isinstance(request, dict):
            return {"ok": False, "error": "Request must be an object"}
        token = request.get("token")
        if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
            return {"ok": False, "error": "Unauthorized"}
        request_id = request.get("id")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 80:
            return {"ok": False, "error": "Request needs an id of 1..80 characters"}
        params = request.get("params", {})
        if not isinstance(params, dict):
            return {"ok": False, "error": "params must be an object"}
        digest = hashlib.sha256(encode([request.get("method"), params])).hexdigest()
        if request_id in self.cache:
            previous_digest, result = self.cache[request_id]
            if previous_digest != digest:
                return {"ok": False, "error": "Request id reused with different parameters"}
            return result
        try:
            result = {"ok": True, "result": self.engine.dispatch(request.get("method"), params)}
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "type": type(exc).__name__}
        self.cache[request_id] = (digest, result)
        if len(self.cache) > 128:
            self.cache.popitem(last=False)
        return result

    def drop(self, conn):
        self.clients.pop(conn, None)
        conn.close()

    def poll(self):
        if self.closed:
            return None
        # Each tick bounds network work. Blender operations themselves can block.
        for _ in range(MAX_CLIENTS):
            try:
                conn, _ = self.socket.accept()
            except BlockingIOError:
                break
            conn.setblocking(False)
            if len(self.clients) >= MAX_CLIENTS:
                conn.close()
            else:
                self.clients[conn] = {"input": bytearray(), "output": None, "since": time.monotonic()}
        executed = False
        for conn, state in list(self.clients.items()):
            try:
                if state["output"] is None:
                    if time.monotonic() - state["since"] > 10:
                        self.drop(conn)
                        continue
                    try:
                        data = conn.recv(65536)
                    except BlockingIOError:
                        data = None
                    if data == b"":
                        self.drop(conn)
                        continue
                    if data:
                        state["input"].extend(data)
                    if len(state["input"]) > MAX_REQUEST:
                        state["output"] = encode({"ok": False, "error": "Request too large"})
                    elif b"\n" in state["input"] and not executed:
                        try:
                            request = json.loads(
                                state["input"].split(b"\n", 1)[0],
                                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
                            )
                            state["output"] = encode(self.handle(request))
                        except (ValueError, TypeError, UnicodeError):
                            state["output"] = encode({"ok": False, "error": "Invalid JSON request"})
                        state["since"] = time.monotonic()
                        executed = True
                if state["output"] is not None:
                    try:
                        count = conn.send(state["output"])
                        state["output"] = state["output"][count:]
                    except BlockingIOError:
                        pass
                    if not state["output"] or time.monotonic() - state["since"] > 10:
                        self.drop(conn)
            except OSError:
                self.drop(conn)
        return 0.02 if self.clients else 0.1

    def close(self):
        if self.closed:
            return
        self.closed = True
        for conn in list(self.clients):
            self.drop(conn)
        self.socket.close()
        try:
            if json.loads(self.descriptor.read_text())["token"] == self.token:
                self.descriptor.unlink()
        except (OSError, ValueError, KeyError):
            pass
