import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "test-queue.py"


def load_queue():
    spec = importlib.util.spec_from_file_location("test_queue_runtime", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config()

    def config(self, **extra):
        queue = {"dataDir": ".work/queue", "timeoutSeconds": 5}
        queue.update(extra)
        (self.root / "gate.config.json").write_text(json.dumps({"testQueue": queue}), encoding="utf-8")

    def run_queue(self, command, label="dev"):
        return subprocess.run([sys.executable, str(SCRIPT), "run", "--label", label, "--"] + command,
                              cwd=self.root, capture_output=True, text=True, check=False, timeout=15, shell=False)

    def rows(self):
        return [json.loads(line) for line in (self.root / ".work/queue/runs.jsonl").read_text(
            encoding="utf-8").splitlines()]

    def test_argv_is_literal_and_exit_status_and_log_are_preserved(self):
        marker = str(self.root / "argument.txt")
        text = "spaces & ; $(must-stay-literal) 中文"
        code = "import pathlib,sys;pathlib.Path(sys.argv[1]).write_text(sys.argv[2],encoding='utf-8');sys.exit(3)"
        result = self.run_queue([sys.executable, "-c", code, marker, text])
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(Path(marker).read_text(encoding="utf-8"), text)
        row = self.rows()[-1]
        self.assertEqual((row["outcome"], row["exitCode"], row["label"]), ("fail", 3, "dev"))
        self.assertEqual(row["argv"][-1], text)

    def test_default_mode_blocks_full_suite_before_start(self):
        result = self.run_queue([sys.executable, "-m", "unittest", "discover"])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("target", result.stderr.lower())
        self.assertFalse((self.root / ".work/queue/runs.jsonl").exists())

    def test_target_file_runs_without_node_or_system_shell(self):
        path = self.root / "test_target.py"
        path.write_text("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertEqual(2+2,4)\n", encoding="utf-8")
        result = self.run_queue([sys.executable, "-m", "unittest", "test_target.py"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.rows()[-1]["outcome"], "pass")

    def test_timeout_kills_descendant_before_it_can_write(self):
        self.config(timeoutSeconds=1)
        marker = self.root / "should-not-exist"
        child = "import time,pathlib;time.sleep(2);pathlib.Path(%r).write_text('alive')" % str(marker)
        parent = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',sys.argv[1]]);time.sleep(10)"
        result = self.run_queue([sys.executable, "-c", parent, child])
        self.assertEqual(result.returncode, 124, result.stderr)
        time.sleep(1.5)
        self.assertFalse(marker.exists(), "a descendant survived the timeout")
        self.assertEqual(self.rows()[-1]["outcome"], "timeout")

    def test_missing_executable_is_recorded_as_command_error(self):
        result = self.run_queue([str(self.root / "no-such-executable")])
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assertEqual(self.rows()[-1]["outcome"], "command_error")

    def test_advanced_pool_accounting_and_heavy_isolation(self):
        module = load_queue()
        cfg = {"mode": "advanced", "slots": 20, "minTestSlots": 2, "minFreeGB": 8, "heavyMax": 1}
        state = {"holders": [{"weight": 3, "heavy": True}], "waiters": [{"id": "h", "heavy": True}, {"id": "l", "heavy": False}]}
        self.assertEqual(module.test_limit(cfg, state, 10, 32 * 2 ** 30), 13)
        self.assertEqual(module.test_limit(cfg, state, 10, 2 ** 30), 3)
        self.assertEqual(module.head_of(state, cfg)["id"], "l")
        self.assertTrue(module.can_grant({"holders": []}, {"weight": 10}, 2))

    def test_sessions_are_read_only_and_only_counted_when_advanced_enabled(self):
        module = load_queue()
        sessions = self.root / "sessions"
        sessions.mkdir()
        (sessions / "one.jsonl").write_text("{}\n", encoding="utf-8")
        cfg = {"mode": "targeted", "poolCountsSessions": True, "activeSessionMinutes": 10,
               "sessionDirs": [{"path": str(sessions), "depth": 1, "ext": ".jsonl"}]}
        self.assertEqual(module.active_sessions(cfg), 0)
        cfg["mode"] = "advanced"
        self.assertEqual(module.active_sessions(cfg), 1)
        self.assertEqual((sessions / "one.jsonl").read_text(encoding="utf-8"), "{}\n")

    def test_shared_runner_captures_bytes_and_passes_environment(self):
        from tools.lib.process_runner import run_command
        environment = dict(os.environ, QUEUE_TEST_VALUE="literal & value")
        result = run_command([sys.executable, "-c", "import os,sys;sys.stdout.buffer.write(os.environ['QUEUE_TEST_VALUE'].encode());sys.stderr.buffer.write(b'error')"],
                             capture_output=True, text=False, env=environment, timeout=5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"literal & value", b"error"))

    def test_shared_runner_timeout_returns_partial_bytes_and_kills_tree(self):
        from tools.lib.process_runner import run_command
        marker = self.root / "captured-child-survived"
        child = "import time,pathlib;time.sleep(1.5);pathlib.Path(%r).write_text('alive')" % str(marker)
        parent = "import subprocess,sys,time;print('started',flush=True);subprocess.Popen([sys.executable,'-c',sys.argv[1]]);time.sleep(10)"
        with self.assertRaises(subprocess.TimeoutExpired) as captured:
            run_command([sys.executable, "-c", parent, child], capture_output=True, text=False, timeout=0.5)
        self.assertIn(b"started", captured.exception.stdout)
        time.sleep(1.2)
        self.assertFalse(marker.exists())

    def test_advanced_one_slot_serializes_independent_queue_processes(self):
        self.config(mode="advanced", slots=1, minTestSlots=1, poolCountsSessions=False, minFreeGB=0, pollMs=30)
        events = self.root / "events.jsonl"
        code = "import json,sys,time;f=open(sys.argv[1],'a');f.write(json.dumps({'event':'start','tag':sys.argv[2]})+'\\n');f.flush();time.sleep(.2);f.write(json.dumps({'event':'stop','tag':sys.argv[2]})+'\\n');f.close()"
        processes = [subprocess.Popen([sys.executable, str(SCRIPT), "run", "--label", tag, "--", sys.executable,
                     "-c", code, str(events), tag], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False) for tag in ("a", "b")]
        failure, outputs = None, []
        try:
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired as error:
                    state = self.root / ".work/queue/state.json"
                    details = state.read_text(encoding="utf-8") if state.exists() else "missing state"
                    failure = "queue hung: pids/status=%r state=%s" % ([(p.pid, p.poll()) for p in processes], details)
                    break
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                outputs.append(process.communicate(timeout=5))
        if failure:
            self.fail(failure + " outputs=" + repr(outputs))
        for process, output in zip(processes, outputs):
            self.assertEqual(process.returncode, 0, output)
        rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["event"] for row in rows], ["start", "stop", "start", "stop"])
        self.assertEqual(rows[0]["tag"], rows[1]["tag"])
        self.assertNotEqual(rows[0]["tag"], rows[2]["tag"])


if __name__ == "__main__":
    unittest.main()
