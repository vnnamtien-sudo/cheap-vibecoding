import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "hooks" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def config(self, value):
        (self.root / "gate.config.json").write_text(json.dumps(value), encoding="utf-8")

    def event(self, tool, args):
        return {"hook_event_name": "PreToolUse", "cwd": str(self.root),
                "tool_name": tool, "tool_input": args}

    def hook(self, script, value):
        return subprocess.run([sys.executable, str(ROOT / "hooks" / script)],
                              input=value, text=True, capture_output=True, check=False, shell=False)

    def test_read_range_and_literal_dump_use_project_limit(self):
        self.config({"readLimitLines": 12})
        (self.root / "long.txt").write_text("line\n" * 13, encoding="utf-8")
        decide = load_script("read-limit-hook").decide
        self.assertIn("12", decide(self.event("Read", {"file_path": "long.txt"})))
        self.assertIsNone(decide(self.event("Read", {"limit": 12})))
        self.assertIsNone(decide(self.event("Read", {"limit": "12"})))
        for limit in (13, -1, 0, True, "nan"):
            self.assertIsNotNone(decide(self.event("Read", {"limit": limit})))
        self.assertIsNotNone(decide(self.event("Bash", {"command": "cat long.txt"})))
        self.assertIsNone(decide(self.event("Bash", {"command": "git status"})))

    def test_short_empty_and_binary_files_do_not_trigger_full_read_denial(self):
        self.config({"readLimitLines": 12})
        module = load_script("read-limit-hook")
        for name, content in (("short", b"one\ntwo"), ("empty", b""), ("binary", b"\x00" * 40)):
            path = self.root / name
            path.write_bytes(content)
            self.assertIsNone(module.decide(self.event("Read", {"file_path": name})))

    def test_bad_configuration_and_bad_json_produce_claude_denial(self):
        (self.root / "gate.config.json").write_text("{broken", encoding="utf-8")
        for value in (json.dumps(self.event("Read", {"limit": 1})), "{broken", "[]"):
            result = self.hook("read-limit-hook.py", value)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual(output["hookEventName"], "PreToolUse")
            self.assertEqual(output["permissionDecision"], "deny")
            self.assertTrue(output["permissionDecisionReason"])

    def test_allowed_read_emits_no_protocol_noise(self):
        self.config({"readLimitLines": 12})
        result = self.hook("read-limit-hook.py", json.dumps(self.event("Read", {"limit": 4})))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_test_hook_is_opt_in_and_checks_each_command_segment(self):
        module = load_script("test-queue-hook")
        command = self.event("Bash", {"command": "python -m unittest tests/test_a.py"})
        self.config({})
        self.assertIsNone(module.decide(command))
        self.config({"testQueue": {"hookEnabled": True}})
        self.assertIn("queue", module.decide(command).lower())
        queued = "python tools/test-queue.py run --label unit -- python -m unittest tests/test_a.py"
        self.assertIsNone(module.decide(self.event("Bash", {"command": queued})))
        self.assertIsNotNone(module.decide(self.event("Bash", {"command":
            "python tools/test-queue.py status && python -m unittest tests/test_a.py"})))
        self.assertIsNone(module.decide(self.event("Bash", {"command": "git status"})))

    def test_configured_runner_and_read_disable_remain_supported(self):
        self.config({"readLimit": {"enabled": False}, "testCommand": ["custom-runner", "{files}"],
                     "testQueue": {"hookEnabled": True}})
        self.assertIsNone(load_script("read-limit-hook").decide(self.event("Read", {"limit": 10000})))
        self.assertIsNotNone(load_script("test-queue-hook").decide(
            self.event("Shell", {"command": "custom-runner tests/one.py"})))

    def test_python_placeholder_and_quoted_queue_paths_are_recognized(self):
        self.config({"testCommand": ["{python}", "tools/targeted-tests.py", "{files}"],
                     "testQueue": {"hookEnabled": True}})
        decide = load_script("test-queue-hook").decide
        self.assertIsNotNone(decide(self.event("Bash", {"command": "python tools/targeted-tests.py tests/one.py"})))
        drive = "C" + ":" + "\\"
        command = '"' + drive + 'Program Files\\Python\\python.exe" -m unittest tests.one'
        self.assertIsNotNone(decide(self.event("Bash", {"command": command})))
        queued = 'python "' + drive + 'project with spaces\\tools\\test-queue.py" run --label unit -- ' + command
        self.assertIsNone(decide(self.event("Bash", {"command": queued})))


if __name__ == "__main__":
    unittest.main()
