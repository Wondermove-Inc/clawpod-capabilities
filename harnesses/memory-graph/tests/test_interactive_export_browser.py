import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("semantic_export_browser", ROOT / "semantic_v11.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
API = {"error": ValueError}


class Cdp:
    """Tiny dependency-free DevTools client for browser interaction proof."""
    def __init__(self, url):
        match = re.fullmatch(r"ws://([^/:]+):(\d+)(/.*)", url)
        self.sock = socket.create_connection((match.group(1), int(match.group(2))), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET {match.group(3)} HTTP/1.1\r\nHost: {match.group(1)}:{match.group(2)}\r\n"
                   f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(response.decode(errors="replace"))
        self.ident = 0

    def _read_exact(self, count):
        data = b""
        while len(data) < count:
            data += self.sock.recv(count - len(data))
        return data

    def _receive(self):
        first, second = self._read_exact(2)
        length = second & 127
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        payload = self._read_exact(length)
        if first & 15 == 8:
            raise RuntimeError("DevTools websocket closed")
        return json.loads(payload)

    def call(self, method, params=None):
        self.ident += 1
        body = json.dumps({"id": self.ident, "method": method, "params": params or {}}).encode()
        mask = os.urandom(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(body))
        header = bytes((0x81, 0x80 | (126 if len(body) >= 126 else len(body))))
        if len(body) >= 126:
            header += struct.pack("!H", len(body))
        self.sock.sendall(header + mask + masked)
        while True:
            message = self._receive()
            if message.get("id") == self.ident:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message["result"]

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result["result"].get("value")

    def close(self):
        self.sock.close()


class BrowserInteractionTests(unittest.TestCase):
    def test_real_pointer_drag_and_keyboard_activation(self):
        chromium = shutil.which("chromium") or shutil.which("chromium-browser")
        if not chromium:
            self.skipTest("Chromium is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = {"path": "memory/topic.md", "line_start": 2, "line_end": 2}
            entities = [
                {"proposal_id": "private-person-id", "kind": "entity", "claim_id": "private-claim-id", "source": source,
                 "payload": {"entity_id": "person:private-name", "type": "Person"}, "basis": "private basis", "lifecycle": "candidate"},
                {"proposal_id": "private-decision-id", "kind": "entity", "claim_id": "private-claim-id", "source": source,
                 "payload": {"entity_id": "decision:private-choice", "type": "Decision"}, "basis": "private basis", "lifecycle": "candidate"},
            ]
            assertions = [{"proposal_id": "private-edge-id", "kind": "assertion", "claim_id": "private-claim-id", "source": source,
                           "payload": {"subject": {"entity_id": "person:private-name", "type": "Person"}, "predicate": "decided",
                                       "object": {"entity_id": "decision:private-choice", "type": "Decision"}},
                           "basis": "private rationale", "lifecycle": "candidate"}]
            bundle = {"schema_version": "memory-graph-validated-proposals/v1", "namespace": "private-namespace",
                      "entity_proposals": entities, "assertion_proposals": assertions, "quarantine": []}
            bundle["validated_hash"] = M.sha(bundle)
            output = root / "graph.html"
            M.export_html(bundle, output, API)
            profile = root / "profile"
            cdp = None
            process = subprocess.Popen([chromium, "--headless=new", "--no-sandbox", "--disable-gpu", "--remote-debugging-port=0",
                                        f"--user-data-dir={profile}", output.as_uri()], stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.time() + 10
                websocket = None
                while time.time() < deadline:
                    line = process.stderr.readline()
                    found = re.search(r"DevTools listening on (ws://[^\s]+)", line)
                    if found:
                        port = re.search(r":(\d+)/", found.group(1)).group(1)
                        break
                else:
                    if process.poll() is not None:
                        self.skipTest("Chromium is blocked by the execution sandbox; run this test with browser permissions")
                    self.fail("Chromium did not expose DevTools")
                for _ in range(50):
                    try:
                        targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1))
                        websocket = next(item["webSocketDebuggerUrl"] for item in targets if item["type"] == "page")
                        break
                    except (OSError, StopIteration):
                        time.sleep(.1)
                cdp = Cdp(websocket)
                cdp.call("Runtime.enable")
                for _ in range(50):
                    if cdp.evaluate("document.querySelectorAll('g[role=button]').length===2"):
                        break
                    time.sleep(.1)
                before = cdp.evaluate("(()=>{const c=document.querySelector('g[role=button] circle'),r=c.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,cx:+c.getAttribute('cx')}})()")
                cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": before["x"], "y": before["y"], "button": "left", "buttons": 1, "clickCount": 1})
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": before["x"] + 70, "y": before["y"] + 35, "button": "left", "buttons": 1})
                during = cdp.evaluate("(()=>{const g=document.querySelector('g[role=button]');return {connected:g.isConnected,cx:+g.querySelector('circle').getAttribute('cx')}})()")
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": before["x"] + 70, "y": before["y"] + 35, "button": "left", "buttons": 0, "clickCount": 1})
                self.assertTrue(during["connected"])
                self.assertGreater(abs(during["cx"] - before["cx"]), 40)
                for selector, key, expected in (("g[role=button]", "Enter", '"type": "'), ("path.edge", " ", '"relation": "decided"')):
                    cdp.evaluate(f"document.querySelector('{selector}').focus();document.getElementById('details').textContent='pending'")
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "code": "Space" if key == " " else "Enter"})
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": "Space" if key == " " else "Enter"})
                    self.assertIn(expected, cdp.evaluate("document.getElementById('details').textContent"))
            finally:
                if cdp is not None:
                    cdp.close()
                process.terminate()
                process.wait(timeout=5)
                process.stderr.close()


if __name__ == "__main__":
    unittest.main()
