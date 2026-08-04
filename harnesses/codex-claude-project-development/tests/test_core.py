from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_claude_project_development", PACKAGE / "codex_claude_project_development.py")
assert SPEC and SPEC.loader
cap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cap)

FAKE = '''#!/usr/bin/env python3
import json, os, sys, time
a=sys.argv[1:]; mode=os.environ.get("FAKE_ACPX_MODE", "ok")
if "--version" in a:
 print("acpx " + ("0.2.9" if mode == "old" else "0.3.1")); raise SystemExit()
if mode == "timeout": time.sleep(2)
if "list" in a:
 if mode == "malformed": print("{"); raise SystemExit()
 print(json.dumps({"source":"local" if mode == "capability" else "agent","sessions":[]})); raise SystemExit()
if "ensure" in a:
 if mode == "auth": print("authentication required",file=sys.stderr); raise SystemExit(1)
 if mode == "malformed_ensure": print(json.dumps({"name":"wrong"})); raise SystemExit()
 name=a[a.index("--name")+1]
 print(json.dumps({"name":name,"acpxRecordId":"record-1","acpxSessionId":"acpx-1","agentSessionId":"agent-1"})); raise SystemExit()
if "prompt" in a:
 sys.stdin.read()
 print(json.dumps({"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"FAKE_RESPONSE"}}}}))
 print(json.dumps({"jsonrpc":"2.0","id":"req-1","result":{"stopReason":"end_turn"}})); raise SystemExit()
if "close" in a: print(json.dumps({"closed":True})); raise SystemExit()
raise SystemExit(1)
'''


class ContinuityCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.cwd = self.repo / "work"
        self.cwd.mkdir(parents=True)
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / "tracked").write_text("one")
        subprocess.run(["git", "-C", str(self.repo), "add", "tracked"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-m", "initial"], check=True, capture_output=True)
        self.head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.state_root = self.root / "state"; self.state_root.mkdir()
        self.state = self.state_root / "continuity.json"
        self.fake = self.root / "acpx"; self.fake.write_text(FAKE); self.fake.chmod(0o700)

    def tearDown(self) -> None: self.temporary.cleanup()
    def invoke(self, *arguments: str): return cap.run(cap.build_parser().parse_args(list(arguments)))
    def store(self): return ["--state-file", str(self.state), "--state-root", str(self.state_root)]
    def context(self, agent="codex", branch="main", head=None):
        return [*self.store(), "--project-id", "project-1", "--workspace-root", str(self.root), "--repo", str(self.repo), "--cwd", str(self.cwd), "--branch", branch, "--head", head or self.head, "--agent", agent]
    def onboard(self): return self.invoke("onboard", *self.store(), "--agent", "both", "--expected-revision", "0")
    def register(self):
        c=self.context(); del c[-2:]
        return self.invoke("project-register", *c, "--expected-revision", "1")
    def ready(self): self.onboard(); self.register()
    def run_turn(self, revision=2, token="lease-a", rotate=False, prompt="private prompt"):
        argv=["session-run",*self.context(),"--acpx-binary",str(self.fake),"--prompt-file","-","--lease-token",token,"--now","10","--expires-at","20","--timeout-seconds","1","--expected-revision",str(revision)]
        if rotate: argv.append("--rotate")
        with mock.patch("sys.stdin", io.StringIO(prompt)): return self.invoke(*argv)

    def test_fake_acpx_success_repeat_rotation_and_no_raw_storage(self):
        self.ready(); first=self.run_turn(); second=self.run_turn(revision=4)
        self.assertEqual(first["sessionName"], second["sessionName"])
        self.assertEqual(first["response"], "FAKE_RESPONSE")
        self.assertEqual(second["generation"], 1)
        rotated=self.run_turn(revision=6, rotate=True)
        self.assertEqual(rotated["generation"], 2)
        raw=self.state.read_text()
        self.assertNotIn("private prompt", raw); self.assertNotIn("jsonrpc", raw); self.assertNotIn("FAKE_RESPONSE", raw)
        self.assertEqual(self.invoke("session-resolve", *self.context())["acpxSessionId"], "acpx-1")
        self.invoke("session-close", *self.context(), "--acpx-binary", str(self.fake), "--timeout-seconds", "1", "--expected-revision", "8")
        with self.assertRaises(cap.Failure): self.invoke("session-resolve", *self.context())

    def test_missing_version_capability_auth_malformed_and_timeout_fail_closed(self):
        self.ready()
        missing=self.root/"missing"
        cases=[("missing", {"acpx_binary":str(missing)}, "acpx_missing"), ("old",{},"acpx_version"), ("capability",{},"acpx_capability"), ("auth",{},"acpx_auth_failed"), ("malformed",{},"acpx_malformed_output"), ("malformed_ensure",{},"acpx_malformed_output"), ("timeout",{},"acpx_timeout")]
        revision=2
        for mode, overrides, code in cases:
            with self.subTest(mode=mode), mock.patch.dict(os.environ,{"FAKE_ACPX_MODE":mode}):
                argv=["session-run",*self.context(),"--acpx-binary",overrides.get("acpx_binary",str(self.fake)),"--prompt-file","-","--lease-token","lease-a","--now","10","--expires-at","20","--timeout-seconds","1","--expected-revision",str(revision)]
                with mock.patch("sys.stdin",io.StringIO("x")), self.assertRaises(cap.Failure) as caught: self.invoke(*argv)
                self.assertEqual(caught.exception.code,code)
            revision += 2  # acquire and fail-path release are both durable CAS writes
            state=json.loads(self.state.read_text()); self.assertEqual(state["projects"]["project-1"]["leases"],{})

    def test_stale_lease_branch_cwd_head_and_secret_redaction(self):
        self.ready()
        self.invoke("lease-acquire",*self.context(),"--lease-token","old","--now","1","--expires-at","5","--expected-revision","2")
        # Expired leases are recoverable; active foreign leases fail.
        with mock.patch("sys.stdin",io.StringIO("x")):
            result=self.invoke("session-run",*self.context(),"--acpx-binary",str(self.fake),"--prompt-file","-","--lease-token","new","--now","6","--expires-at","20","--timeout-seconds","1","--expected-revision","3")
        self.assertTrue(result["result"]["completed"])
        with self.assertRaises(cap.Failure): self.invoke("session-resolve",*self.context(branch="other"))
        outside=self.repo/"other"; outside.mkdir()
        bad=self.context(); bad[bad.index("--cwd")+1]=str(outside)
        with self.assertRaises(cap.Failure): self.invoke("session-resolve",*bad)
        (self.repo/"tracked").write_text("two"); subprocess.run(["git","-C",str(self.repo),"commit","-am","next"],check=True,capture_output=True)
        with self.assertRaises(cap.Failure): self.invoke("session-resolve",*self.context())
        self.assertNotIn("private prompt", self.state.read_text())
        with self.assertRaisesRegex(cap.Failure,"branch is invalid"):
            c=self.context(branch="Authorization: bearer redacted"); del c[-2:]
            self.invoke("project-register",*c,"--expected-revision","5")

if __name__ == "__main__": unittest.main()
