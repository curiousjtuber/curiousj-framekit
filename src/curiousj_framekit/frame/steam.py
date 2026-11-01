"""The running Steam client, through its Chromium debug port. On the
Frame, Steam runs with that port open on 127.0.0.1:8080 for the VR
shell, and the client's own JavaScript API can read and set a game's
launch options and save them. The client's file, localconfig.vdf, can't
be edited instead while Steam runs, as it writes its copy back over it.

A WebSocket by hand, to keep to the standard library."""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import urllib.request

from ..cmdline import Error

PORT = 8080


class Client:
    """One connection to the client's SharedJSContext page, the one with
    the stores and SteamClient."""

    def __init__(self, port: int = PORT, timeout: float = 15):
        self.port = port
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as r:
                targets = json.load(r)
            target = next(t for t in targets if t.get("title") == "SharedJSContext")
        except (OSError, StopIteration, ValueError):
            raise Error(f"Steam's debug port isn't open on 127.0.0.1:{port}") from None
        path = target["webSocketDebuggerUrl"].split(f":{port}", 1)[1]
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n".encode())
        self.buf = b""
        while b"\r\n\r\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise Error("the debug port closed the connection")
            self.buf += chunk
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise Error("the debug port refused the WebSocket")
        self.next_id = 1

    def close(self) -> None:
        self.sock.close()

    def send(self, obj: dict) -> None:
        self.sock.sendall(frame(json.dumps(obj).encode()))

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise Error("the debug port closed the connection")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> dict:
        b0, b1 = self._read(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._read(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._read(8))[0]
        if b1 & 0x80:
            self._read(4)
        return json.loads(self._read(n))

    def evaluate(self, js: str):
        """Run js in the page, awaiting a promise, and return its value."""
        msg_id = self.next_id
        self.next_id += 1
        self.send({"id": msg_id, "method": "Runtime.evaluate",
                   "params": {"expression": js, "awaitPromise": True, "returnByValue": True}})
        while True:
            reply = self.recv()
            if reply.get("id") == msg_id:
                break
        result = reply.get("result", {}).get("result", {})
        if "value" not in result:
            raise Error("the client's answer made no sense: " + json.dumps(reply)[:300])
        return result["value"]


def frame(data: bytes) -> bytes:
    """One masked text frame, as a client must send."""
    n = len(data)
    if n < 126:
        size = bytes([0x80 | n])
    elif n < 65536:
        size = b"\xfe" + struct.pack(">H", n)
    else:
        size = b"\xff" + struct.pack(">Q", n)
    mask = os.urandom(4)
    return b"\x81" + size + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data))


LAUNCH_OPTIONS_JS = """(async () => {
  const id = %d, hook = %s, tick = () => new Promise(r => setTimeout(r, 100));
  for (let i = 0; i < 50 && !appDetailsStore.GetAppDetails(id); i++) {
    if (!i) appDetailsStore.RequestAppDetails(id);
    await tick();
  }
  const details = appDetailsStore.GetAppDetails(id);
  if (!details) return { error: "the client has no details for app " + id };
  const was = details.strLaunchOptions;
  if (hook === null || (was !== "" && !%s)) return { was };
  await SteamClient.Apps.SetAppLaunchOptions(id, hook);
  for (let i = 0; i < 50 && appDetailsStore.GetAppDetails(id).strLaunchOptions !== hook; i++) await tick();
  return { was, now: appDetailsStore.GetAppDetails(id).strLaunchOptions };
})()"""


def launch_options(appid: int, set_to: str | None = None, force: bool = False) -> dict:
    """Read a game's launch options, or set them: {"was": old} when only
    read or left alone, {"was": old, "now": new} when set. Without force,
    options that are already set are left alone, since there is no
    telling what to keep."""
    client = Client()
    try:
        js = LAUNCH_OPTIONS_JS % (appid, json.dumps(set_to), "true" if force else "false")
        result = client.evaluate(js)
    finally:
        client.close()
    if not isinstance(result, dict):
        raise Error("the client's answer made no sense: " + repr(result)[:300])
    if "error" in result:
        raise Error(result["error"])
    return result
