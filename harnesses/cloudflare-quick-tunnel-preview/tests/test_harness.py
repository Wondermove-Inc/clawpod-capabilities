import argparse
import contextlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cloudflare_quick_tunnel_preview.py"
spec = importlib.util.spec_from_file_location("quick_tunnel", CLI)
qt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qt)


def valid_state(binary_path="/bin/true"):
    return {
        "schemaVersion": 1,
        "instanceId": "a" * 32,
        "pid": 123,
        "pidStart": "456",
        "binary": {
            "path": binary_path,
            "sha256": "b" * 64,
            "device": 1,
            "inode": 2,
        },
        "supervisorPid": 124,
        "supervisorStart": "457",
        "supervisorBinary": {
            "path": sys.executable,
            "sha256": "c" * 64,
            "device": 3,
            "inode": 4,
        },
        "url": "https://safe-name.trycloudflare.com",
        "target": "http://127.0.0.1:8000",
        "createdAt": 1000.0,
        "expiresAt": 1030.0,
        "logName": "cloudflared-" + "a" * 32 + ".log",
    }


class UnitTests(unittest.TestCase):
    def test_url_is_strict(self):
        self.assertTrue(qt.valid_url("https://safe-name.trycloudflare.com"))
        invalid = (
            "http://x.trycloudflare.com", "https://trycloudflare.com",
            "https://x.trycloudflare.com.evil", "https://x.trycloudflare.com/path",
            "https://u:p@x.trycloudflare.com", "https://x.trycloudflare.com:443",
            "https://-x.trycloudflare.com", None, 4,
        )
        for value in invalid:
            self.assertFalse(qt.valid_url(value), value)

    def test_loopback_only_and_port(self):
        self.assertEqual(qt.validated_target("127.0.0.1", 1, False), "http://127.0.0.1:1")
        self.assertEqual(qt.validated_target("::1", 2, False), "http://[::1]:2")
        for host in ("localhost", "0.0.0.0", "192.168.1.2"):
            with self.assertRaises(qt.Fail):
                qt.validated_target(host, 8000, False)
        for port in (True, 0, 65536, "8000"):
            with self.assertRaises(qt.Fail):
                qt.validated_target("127.0.0.1", port, False)

    def test_binary_rejects_relative_symlink_and_unsafe_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cloudflared"
            path.write_text("#!/bin/sh\n")
            path.chmod(0o755)
            self.assertEqual(qt.inspect_binary(str(path))["path"], str(path))
            with self.assertRaises(qt.Fail):
                qt.inspect_binary("relative")
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(qt.Fail):
                qt.inspect_binary(str(link))
            path.chmod(0o775)
            with self.assertRaises(qt.Fail):
                qt.inspect_binary(str(path))

    def test_auth_environment_is_checked_by_allowlist(self):
        with mock.patch.dict(os.environ, {"TUNNEL_TOKEN": "present"}, clear=False):
            with self.assertRaises(qt.Fail) as caught:
                qt.reject_auth_state()
        self.assertEqual(caught.exception.code, "AUTH_STATE_PRESENT")
        with mock.patch.object(qt.os, "environ", {"UNRELATED_SECRET": "ignored"}):
            with mock.patch.object(qt.Path, "home", return_value=Path("/nonexistent")):
                qt.reject_auth_state()

    def test_every_state_field_is_validated(self):
        mutations = {
            "schemaVersion": 2, "instanceId": "bad", "pid": True,
            "pidStart": "0", "url": "https://evil.example", "target": "http://0.0.0.0:1",
            "supervisorPid": True, "supervisorStart": "0",
            "createdAt": float("nan"), "expiresAt": 999.0, "logName": "other.log",
        }
        for field, value in mutations.items():
            state = valid_state(); state[field] = value
            with self.assertRaises(qt.Fail, msg=field):
                qt.validate_state(state)
        for container in ("binary", "supervisorBinary"):
            for field, value in (("path", "relative"), ("sha256", "x"), ("device", -1), ("inode", True)):
                state = valid_state(); state[container][field] = value
                with self.assertRaises(qt.Fail, msg=container + field):
                    qt.validate_state(state)
        state = valid_state(); state["extra"] = 1
        with self.assertRaises(qt.Fail):
            qt.validate_state(state)

    def test_unsafe_state_and_lock_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o755)
            with self.assertRaises(qt.Fail):
                qt.secure_root(root)
            root.chmod(0o700)
            with qt.state_lock(root):
                self.assertEqual((root / "lock").stat().st_mode & 0o777, 0o600)
            (root / "lock").chmod(0o644)
            with self.assertRaises(qt.Fail):
                with qt.state_lock(root):
                    pass

    def test_inspect_does_not_return_logs(self):
        state = valid_state()
        args = argparse.Namespace(state_root="/state")
        with mock.patch.object(qt, "state_lock") as lock, mock.patch.object(qt, "load_state", return_value=state), mock.patch.object(qt, "process_is_owned", return_value=True), mock.patch.object(qt, "supervisor_is_owned", return_value=True):
            lock.return_value.__enter__.return_value = Path("/state")
            data = qt.command_inspect(args)["data"]
        self.assertNotIn("logs", data)
        self.assertNotIn("diagnostic", data)

    def test_changed_binary_and_foreign_pid_fail_closed(self):
        state = valid_state(sys.executable)
        with mock.patch.object(qt, "process_start", return_value="different"):
            with self.assertRaises(qt.Fail) as caught:
                qt.process_is_owned(state)
        self.assertEqual(caught.exception.code, "FOREIGN_PID")
        with mock.patch.object(qt, "process_start", return_value=state["pidStart"]), mock.patch.object(qt.os, "readlink", return_value=sys.executable), mock.patch.object(qt, "inspect_binary", return_value={**state["binary"], "sha256": "c" * 64}):
            with self.assertRaises(qt.Fail) as caught:
                qt.process_is_owned(state)
        self.assertEqual(caught.exception.code, "BINARY_CHANGED")

    def test_reaper_identity_cannot_kill_replacement(self):
        state = valid_state()
        args = argparse.Namespace(state_root="/state", expires_at=state["expiresAt"], expected_instance="c" * 32, expected_pid=state["pid"], expected_pid_start=state["pidStart"], expected_supervisor_pid=state["supervisorPid"], expected_supervisor_start=state["supervisorStart"])
        with mock.patch.object(qt.time, "sleep"), mock.patch.object(qt.time, "time", return_value=2000), mock.patch.object(qt.Path, "exists", return_value=True), mock.patch.object(qt, "state_lock") as lock, mock.patch.object(qt, "load_state", return_value=state), mock.patch.object(qt, "terminate_owned") as terminate:
            lock.return_value.__enter__.return_value = Path("/state")
            result = qt.command_reap(args)
        self.assertFalse(result["data"]["changed"])
        terminate.assert_not_called()

    def test_stale_stop_reconciles_idempotently(self):
        state = valid_state()
        args = argparse.Namespace(state_root="/state")
        with mock.patch.object(qt.Path, "exists", return_value=True), mock.patch.object(qt, "state_lock") as lock, mock.patch.object(qt, "load_state", side_effect=[state, None]), mock.patch.object(qt, "process_is_owned", return_value=False), mock.patch.object(qt, "supervisor_is_owned", return_value=False), mock.patch.object(qt, "remove_artifacts") as remove:
            lock.return_value.__enter__.return_value = Path("/state")
            first = qt.command_stop(args); second = qt.command_stop(args)
        self.assertTrue(first["data"]["reconciled"])
        self.assertFalse(second["data"]["changed"])
        remove.assert_called_once()

    def test_cleanup_spawned_term_then_kill_is_bounded(self):
        process = mock.Mock(pid=44)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("x", 3), None]
        qt.cleanup_spawned(process, "1")
        process.terminate.assert_called_once(); process.kill.assert_called_once()


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("cc") is None:
            raise unittest.SkipTest("C compiler unavailable")
        cls.build = tempfile.TemporaryDirectory()
        source = Path(cls.build.name) / "fake.c"
        cls.binary = Path(cls.build.name) / "cloudflared"
        source.write_text(r'''#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static volatile int run=1; void h(int x){run=0;}
int main(int argc,char**argv){char p[4096];signal(SIGTERM,h);snprintf(p,sizeof(p),"%s/early",getenv("HOME"));if(access(p,F_OK)==0)return 7;snprintf(p,sizeof(p),"%s/spam",getenv("HOME"));if(access(p,F_OK)==0){for(int i=0;i<200000;i++)fputs("0123456789abcdef",stderr);fputs("token=supersecret\n",stderr);}snprintf(p,sizeof(p),"%s/silent",getenv("HOME"));if(access(p,F_OK)!=0){fprintf(stderr,"https://safe-name.trycloudflare.com\n");fflush(stderr);}while(run)sleep(1);return 0;}''')
        subprocess.run(["cc", "-O2", "-o", str(cls.binary), str(source)], check=True)
        cls.binary.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def call(self, *args, env=None):
        return subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True, env=env)

    @contextlib.contextmanager
    def listener(self):
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen()
        stop = threading.Event()
        def accept():
            while not stop.is_set():
                try: server.settimeout(.1); connection, _ = server.accept(); connection.close()
                except (socket.timeout, OSError): pass
        thread = threading.Thread(target=accept); thread.start()
        try: yield server.getsockname()[1]
        finally: stop.set(); server.close(); thread.join()

    def start_args(self, root, port, timeout="3"):
        return ("start", "--state-root", str(root), "--cloudflared", str(self.binary), "--host", "127.0.0.1", "--port", str(port), "--ttl", "30", "--discovery-timeout", timeout)

    def test_installed_entrypoint_preflight_and_idempotent_stop(self):
        with tempfile.TemporaryDirectory() as directory, self.listener() as port:
            root = Path(directory) / "state"
            preflight = self.call("preflight", "--state-root", str(root), "--cloudflared", str(self.binary), "--port", str(port))
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            self.assertTrue(json.loads(preflight.stdout)["data"]["ready"])
            stopped = self.call("stop", "--state-root", str(root))
            self.assertFalse(json.loads(stopped.stdout)["data"]["changed"])

    def test_concurrent_starts_create_only_one_tunnel(self):
        with tempfile.TemporaryDirectory() as directory, self.listener() as port:
            root = Path(directory) / "state"
            command = [sys.executable, str(CLI), *self.start_args(root, port)]
            first = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            second = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            outputs = [first.communicate(timeout=10), second.communicate(timeout=10)]
            codes = [first.returncode, second.returncode]
            self.assertEqual(sorted(codes), [0, 2], outputs)
            errors = [json.loads(output[0]).get("error", {}).get("code") for output in outputs]
            self.assertIn("ALREADY_RUNNING", errors)
            self.call("stop", "--state-root", str(root))

    def test_early_death_and_timeout_cleanup(self):
        with tempfile.TemporaryDirectory() as directory, self.listener() as port:
            for name, code in (("early", "EARLY_DEATH"), ("silent", "DISCOVERY_TIMEOUT")):
                root = Path(directory) / name
                root.mkdir(mode=0o700)
                (root / name).touch()
                response = self.call(*self.start_args(root, port, "1"))
                self.assertEqual(json.loads(response.stdout)["error"]["code"], code)
                self.assertFalse((root / "state.json").exists())
                self.assertEqual(list(root.glob("cloudflared-*.log")), [])

    def test_save_failure_cleans_real_child(self):
        with tempfile.TemporaryDirectory() as directory, self.listener() as port:
            root = Path(directory) / "state"
            args = qt.parser().parse_args(self.start_args(root, port))
            captured = {}
            real_popen = subprocess.Popen
            def capture(*a, **kw):
                process = real_popen(*a, **kw); captured["process"] = process; return process
            with mock.patch.object(qt, "save_state", side_effect=OSError("disk failure")), mock.patch.object(qt.subprocess, "Popen", side_effect=capture):
                with self.assertRaises(OSError): qt.command_start(args)
            self.assertIsNotNone(captured["process"].poll())
            self.assertFalse((root / "state.json").exists())
            self.assertEqual(list(root.glob("cloudflared-*.log")), [])

    def test_output_is_bounded_and_stop_cleans_supervisor_and_child(self):
        with tempfile.TemporaryDirectory() as directory, self.listener() as port:
            root = Path(directory) / "state"; root.mkdir(mode=0o700); (root / "spam").touch()
            response = self.call(*self.start_args(root, port, "5"))
            self.assertEqual(response.returncode, 0, response.stdout)
            state = json.loads((root / "state.json").read_text())
            log_path = root / state["logName"]
            self.assertLessEqual(log_path.stat().st_size, qt.MAX_READ_LOG)
            self.assertNotIn(b"supersecret", log_path.read_bytes())
            self.assertTrue(qt.valid_url(json.loads(response.stdout)["data"]["url"]))
            stopped = self.call("stop", "--state-root", str(root))
            self.assertEqual(stopped.returncode, 0, stopped.stdout)
            self.assertTrue(qt.wait_until_dead(state["pid"], state["pidStart"], 2))
            self.assertTrue(qt.wait_until_dead(state["supervisorPid"], state["supervisorStart"], 2))
            self.assertFalse(log_path.exists())

    def test_supervisor_death_cannot_orphan_child(self):
        with tempfile.TemporaryDirectory() as directory, self.listener() as port:
            root = Path(directory) / "state"
            response = self.call(*self.start_args(root, port, "3"))
            self.assertEqual(response.returncode, 0, response.stdout)
            state = json.loads((root / "state.json").read_text())
            os.kill(state["supervisorPid"], 9)
            self.assertTrue(qt.wait_until_dead(state["pid"], state["pidStart"], 3))
            stopped = self.call("stop", "--state-root", str(root))
            self.assertEqual(stopped.returncode, 0, stopped.stdout)
            self.assertTrue(json.loads(stopped.stdout)["data"]["reconciled"])

    def test_reap_cleans_supervisor_and_child(self):
        with tempfile.TemporaryDirectory() as directory, self.listener() as port:
            root = Path(directory) / "state"
            response = self.call(*self.start_args(root, port, "3"))
            self.assertEqual(response.returncode, 0, response.stdout)
            state = json.loads((root / "state.json").read_text())
            state["createdAt"] = time.time() - 1
            state["expiresAt"] = time.time() - .1
            qt.save_state(root, state)
            reap = self.call("_reap", "--state-root", str(root), "--expected-instance", state["instanceId"], "--expected-pid", str(state["pid"]), "--expected-pid-start", state["pidStart"], "--expected-supervisor-pid", str(state["supervisorPid"]), "--expected-supervisor-start", state["supervisorStart"], "--expires-at", str(state["expiresAt"]))
            self.assertEqual(reap.returncode, 0, reap.stdout)
            self.assertTrue(qt.wait_until_dead(state["pid"], state["pidStart"], 2))
            self.assertTrue(qt.wait_until_dead(state["supervisorPid"], state["supervisorStart"], 2))
            self.assertFalse((root / "state.json").exists())

    def test_manifest_runtime_subset(self):
        manifest = json.loads((ROOT / "harness.json").read_text())
        self.assertEqual(set(manifest["commands"]), {"status", "preflight", "start", "inspect", "stop"})
        allowed = {"readOnly", "writeSafe", "destructive", "externalSideEffect"}
        for command in manifest["commands"].values():
            self.assertTrue(set(command["safetyClasses"]) <= allowed)


if __name__ == "__main__":
    unittest.main()
