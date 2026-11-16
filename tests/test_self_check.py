"""Behavior checks for the portable, fail-closed project gate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "self-check.py"
MAPPER = REPO / "tools" / "targeted-tests.py"
WORK = REPO / ".work" / "python-core-tests"
DEFAULTS = {
    "maxFileLines": 400, "maxFunctionLines": 80, "readLimitLines": 60,
    "bannedPatterns": [], "layers": [], "testCommand": [sys.executable, "-c", "pass", "{files}"],
    "typeCheckCommand": [], "dataCheckCommand": [],
}


class SelfCheckTests(unittest.TestCase):
    def project(self, files=None, config=None):
        WORK.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="gate-", dir=str(WORK))
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.write(root, "gate.config.json", json.dumps(dict(DEFAULTS, **(config or {}))))
        self.write(root, ".gitignore", ".gate/\n.work/\n")
        for name, content in (files or {}).items():
            self.write(root, name, content)
        self.git(root, "init", "--quiet")
        self.git(root, "config", "user.name", "Gate fixture")
        self.git(root, "config", "user.email", "fixture@noreply.invalid")
        self.git(root, "add", ".")
        self.git(root, "-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "baseline")
        return root

    @staticmethod
    def write(root, name, content):
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    def git(self, root, *args):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        result = subprocess.run(["git", *args], cwd=root, env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def check(self, root, *args, cwd=None, receipt=None):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        output = root / (receipt or ".gate/self-check.json")
        self.assertTrue(output.is_file(), result.stdout + result.stderr)
        return result, json.loads(output.read_text(encoding="utf-8"))

    @staticmethod
    def violations(receipt):
        return [item for check in receipt["checks"] for item in check.get("violations", [])]

    def test_only_changed_code_is_structurally_checked(self):
        root = self.project({"old.js": 'eval("old");\n' * 9}, {
            "maxFileLines": 4, "bannedPatterns": [{"pattern": r"eval\s*\(", "description": "No eval"}],
        })
        self.write(root, "src/new.js", "export const total = 1;\n")
        self.write(root, "notes.md", "A changed document.\n")
        result, receipt = self.check(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["codeFiles"], ["src/new.js"])
        self.assertEqual(sum(c["status"] == "skipped" for c in receipt["checks"]), 2)

    def test_changed_text_files_obey_file_and_pattern_limits(self):
        root = self.project(config={"maxFileLines": 2, "bannedPatterns": [{
            "pattern": "FORBIDDEN", "description": "Forbidden project marker",
        }]})
        self.write(root, "notes.txt", "FORBIDDEN\nsecond\nthird\n")
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual({v["rule"] for v in self.violations(receipt)}, {"file-lines", "banned-pattern"})
        self.assertEqual(receipt["limitations"], [])

    def test_file_and_function_limits_ignore_string_and_comment_braces(self):
        root = self.project(config={"maxFileLines": 4, "maxFunctionLines": 3})
        self.write(root, "long.js", 'function long() {\n const braces = "}";\n // }\n return braces;\n}\n')
        self.write(root, "worker.py", "def long():\n    value = 1\n    value += 1\n    return value\n")
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        found = self.violations(receipt)
        self.assertTrue(any(v["rule"] == "file-lines" and v["file"] == "long.js" for v in found))
        functions = {(v["file"], v["lines"]) for v in found if v["rule"] == "function-lines"}
        self.assertEqual(functions, {("long.js", 5), ("worker.py", 4)})

    def test_typescript_arrows_and_methods_are_measured(self):
        root = self.project(config={"maxFunctionLines": 2})
        self.write(root, "worker.ts", "const run = (value: string): string => {\n const x = value;\n return x;\n};\n")
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any(v["rule"] == "function-lines" for v in self.violations(receipt)))

    def test_configured_regex_reports_description(self):
        root = self.project(config={"bannedPatterns": [{
            "pattern": r"\beval\s*\(", "description": "Do not execute dynamic source", "flags": "i",
        }]})
        self.write(root, "unsafe.ts", 'EVAL("source");\n')
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any(v["rule"] == "banned-pattern" and "dynamic" in v["description"]
                            for v in self.violations(receipt)))

    def test_js_ts_import_forms_respect_layers(self):
        layers = [{"name": "app", "path": "src/app", "allow": []},
                  {"name": "data", "path": "src/data", "allow": ["app"]}]
        root = self.project({"src/data/db.ts": "export type Row = {};\n"}, {"layers": layers})
        self.write(root, "src/app/view.ts", 'import type { Row } from "../data/db";\n'
                   'export { Row } from "../data/db";\nconst load = () => import("../data/db");\n')
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum(v["rule"] == "layer-import" for v in self.violations(receipt)), 3)

    def test_python_relative_and_absolute_imports_respect_layers(self):
        layers = [{"path": "src/app", "allow": []}, {"path": "src/data", "allow": []}]
        root = self.project({"src/data/db.py": "value = 1\n"}, {"layers": layers})
        self.write(root, "src/app/view.py", "from ..data import db\nimport src.data.db\n")
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sum(v["rule"] == "layer-import" for v in self.violations(receipt)), 2)

    def test_allowed_layers_and_same_layer_imports_pass(self):
        layers = [{"name": "app", "path": "src/app", "allow": []},
                  {"name": "data", "path": "src/data", "allow": ["app"]}]
        root = self.project({"src/app/view.ts": "export const value = 1;\n"}, {"layers": layers})
        self.write(root, "src/data/db.ts", 'export { value } from "../app/view";\n')
        result, _ = self.check(root)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_commands_run_in_order_and_expand_safe_individual_arguments(self):
        recorder = ("import json, pathlib, sys\n"
                    "p = pathlib.Path('order.json')\n"
                    "old = json.loads(p.read_text()) if p.exists() else []\n"
                    "p.write_text(json.dumps(old + [sys.argv[1:]]))\n")
        root = self.project({"record.py": recorder}, {
            "typeCheckCommand": [sys.executable, "record.py", "type"],
            "testCommand": [sys.executable, "record.py", "tests", "{files}"],
            "dataCheckCommand": [sys.executable, "record.py", "data"],
        })
        self.write(root, "src/has spaces; safe.py", "value = 42\n")
        result, receipt = self.check(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((root / "order.json").read_text()),
                         [["type"], ["tests", "src/has spaces; safe.py"], ["data"]])
        self.assertEqual([c["name"] for c in receipt["checks"]],
                         ["structure", "type-check", "tests", "data-check"])

    def test_self_check_child_mapper_uses_its_own_project_configuration(self):
        runner = ("import pathlib, subprocess, sys\n"
                  "result = subprocess.run([sys.executable, " + repr(str(MAPPER))
                  + ", '--plan', 'tools/check-private.py'], cwd='nested', capture_output=True, "
                  "text=True, encoding='utf-8')\n"
                  "pathlib.Path('nested-outcome.json').write_text(result.stdout, encoding='utf-8')\n"
                  "print(result.stdout)\nraise SystemExit(result.returncode)\n")
        root = self.project({
            "run_nested.py": runner, "tests/test_parent_only.py": "import unittest\n",
            "nested/tools/check-private.py": "value = 1\n",
            "nested/tests/test_nested_only.py": "import unittest\n",
            "nested/gate.config.json": json.dumps({"testMappings": {
                "tools/check-private.py": ["tests/test_nested_only.py"],
            }}),
        }, {"testCommand": [sys.executable, "run_nested.py", "{files}"],
            "testMappings": {"tools/check-private.py": ["tests/test_parent_only.py"]}})
        self.write(root, "changed.py", "value = 2\n")
        result, _ = self.check(root)
        outcome = (root / "nested-outcome.json").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, outcome)
        self.assertEqual(json.loads(outcome)["mappings"]["tools/check-private.py"], ["tests/test_nested_only.py"])

    def test_mapper_honors_selected_external_config_for_the_same_project(self):
        test = "import unittest\nclass Sample(unittest.TestCase):\n    def test_value(self):\n        self.assertTrue(True)\n"
        root = self.project({"tools/check-private.py": "value = 1\n", "tests/__init__.py": "",
                             "tests/test_selected.py": test}, {
            "testMappings": {"tools/check-private.py": ["tests/test_missing.py"]},
        })
        selected = dict(DEFAULTS, testCommand=["{python}", str(MAPPER), "{files}"],
                        testMappings={"tools/check-private.py": ["tests/test_selected.py"]})
        self.write(root, "tools/check-private.py", "value = 2\n")
        with tempfile.TemporaryDirectory(prefix="selected-", dir=str(WORK)) as directory:
            self.write(Path(directory), "selected.json", json.dumps(selected))
            result, receipt = self.check(root, "--config", str(Path(directory) / "selected.json"))
        self.assertEqual(result.returncode, 0, json.dumps(receipt["checks"]))

    def test_command_failure_is_nonzero_and_stops_later_steps(self):
        root = self.project(config={
            "typeCheckCommand": [sys.executable, "-c", "raise SystemExit(9)"],
            "testCommand": [sys.executable, "-c", "open('bad-marker', 'w').write('ran')", "{files}"],
        })
        self.write(root, "changed.py", "answer = 42\n")
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / "bad-marker").exists())
        self.assertTrue(any(c["name"] == "type-check" and c.get("exitCode") == 9 for c in receipt["checks"]))

    def test_invalid_configurations_always_leave_failed_json_receipt(self):
        values = ["{", {"maxFileLines": "400"}, {"bannedPatterns": [{"pattern": "[", "description": "bad"}]},
                  {"testCommand": "python one.py | python two.py"}, {"testCommand": ["python", "all.py"]}]
        for value in values:
            with self.subTest(value=value):
                root = self.project()
                self.write(root, "gate.config.json", value if isinstance(value, str)
                           else json.dumps(dict(DEFAULTS, **value)))
                result, receipt = self.check(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(any(c["name"] == "configuration" and c["status"] == "failed"
                                    for c in receipt["checks"]))

    def test_missing_config_uses_defaults_and_custom_root_config_receipt_work(self):
        root = self.project()
        (root / "gate.config.json").unlink()
        self.write(root, "changed.py", "value = 1\n")
        missing, absent = self.check(root)
        self.assertNotEqual(missing.returncode, 0)
        self.assertTrue(any(c["name"] == "tests" and c["status"] == "failed" for c in absent["checks"]))
        self.write(root, "config/custom.json", json.dumps(dict(DEFAULTS, maxFileLines=1)))
        self.write(root, "changed.py", "value = 1\nvalue = 2\n")
        result, _ = self.check(root, "--root", str(root), "--config", "config/custom.json",
                               "--receipt", "receipts/check.json", cwd=REPO, receipt="receipts/check.json")
        self.assertNotEqual(result.returncode, 0)

    def test_empty_test_command_cannot_claim_code_was_verified(self):
        root = self.project(config={"testCommand": []})
        self.write(root, "changed.py", "value = 1\n")
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any(c["name"] == "tests" and c["status"] == "failed" for c in receipt["checks"]))

    def test_invalid_runtime_extensions_fail_closed_without_tracebacks(self):
        invalid = [{"testQueue": {"mode": "typo"}}, {"testQueue": {"slots": 0}},
                   {"testQueue": {"workerPattern": "no-capture"}},
                   {"tokenUsage": {"sessionRoots": {"unknown": ["logs"]}}},
                   {"tokenUsage": {"prices": [["[", [1, 2]]]}},
                   {"tokenUsage": {"prices": [["model", [-1, 2]]]}},
                   {"stages": {"stages": [{"key": "one", "from": "yesterday"}]}}]
        for extension in invalid:
            with self.subTest(extension=extension):
                root = self.project(config=extension)
                result, receipt = self.check(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(any(c["name"] == "configuration" and c["status"] == "failed"
                                    for c in receipt["checks"]))
                self.assertNotIn("Traceback", result.stderr)

    def test_internal_receipts_do_not_become_new_project_changes(self):
        root = self.project({".gitignore": ""})
        self.write(root, "changed.py", "value = 1\n")
        self.assertEqual(self.check(root)[0].returncode, 0)
        result, receipt = self.check(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(receipt["changedFiles"], ["changed.py"])

    def test_changes_include_staged_unstaged_untracked_and_ignore_deleted_binary(self):
        root = self.project({"staged.py": "x = 1\n", "working.py": "x = 1\n", "gone.py": "x = 1\n"})
        self.write(root, "staged.py", "x = 2\n")
        self.git(root, "add", "staged.py")
        self.write(root, "staged.py", "x = 3\n")
        self.write(root, "working.py", "x = 2\n")
        self.write(root, "new.py", "x = 2\n")
        (root / "gone.py").unlink()
        (root / "binary.bin").write_bytes(b"\x00\xff")
        result, receipt = self.check(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(receipt["changedFiles"], ["new.py", "staged.py", "working.py"])
        self.assertTrue(any(item["file"] == "binary.bin" for item in receipt["ignoredFiles"]))

    def test_binary_or_non_utf8_code_cannot_be_silently_ignored(self):
        for content in (b"\x00\xff", b"value = '\xff'\n"):
            with self.subTest(content=content):
                root = self.project()
                (root / "broken.py").write_bytes(content)
                result, receipt = self.check(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(any(c["status"] == "failed" and "broken.py" in c.get("reason", "")
                                    for c in receipt["checks"]))

    def test_staged_mode_reads_index_source_and_index_config(self):
        root = self.project(config={"maxFileLines": 2})
        self.write(root, "staged.py", "x = 1\n" * 3)
        self.git(root, "add", "staged.py")
        self.write(root, "staged.py", "x = 1\n")
        self.write(root, "unstaged.py", "x = 1\n")
        self.write(root, "gate.config.json", json.dumps(dict(DEFAULTS, maxFileLines=100)))
        result, receipt = self.check(root, "--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(receipt["changedFiles"], ["staged.py"])
        self.assertEqual(receipt["mode"], "staged")
        self.assertTrue(any(v["rule"] == "file-lines" for v in self.violations(receipt)))

    def test_staged_commands_execute_the_index_snapshot(self):
        root = self.project({"check.py": "import pathlib\nassert pathlib.Path('changed.py').read_text() == 'x = 2\\n'\n"}, {
            "testCommand": [sys.executable, "check.py", "{files}"],
        })
        self.write(root, "changed.py", "x = 2\n")
        self.git(root, "add", "changed.py")
        self.write(root, "changed.py", "x = 999\n")
        result, receipt = self.check(root, "--staged")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(receipt["commandSource"], "index-snapshot")
        self.assertEqual((root / "changed.py").read_text(), "x = 999\n")

    def test_no_changes_skips_configured_command_and_unknown_syntax_is_disclosed(self):
        root = self.project(config={"testCommand": [sys.executable, "missing.py", "{files}"]})
        result, receipt = self.check(root)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(any(c["name"] == "tests" and c["status"] == "skipped"
                            and "changed" in c["reason"] for c in receipt["checks"]))
        self.write(root, "main.rs", "fn main() {}\n")
        self.write(root, "gate.config.json", json.dumps(DEFAULTS))
        result, receipt = self.check(root)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(any(".rs" in note and "function" in note.lower() for note in receipt["limitations"]))

    def test_data_changes_run_data_command_without_running_code_tests(self):
        root = self.project(config={
            "dataCheckCommand": [sys.executable, "-c", "open('data-ran', 'w').write('yes')", "{files}"],
            "testCommand": [sys.executable, "missing.py", "{files}"],
        })
        self.write(root, "data/values.csv", "name,value\na,2\n")
        result, receipt = self.check(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((root / "data-ran").read_text(), "yes")
        self.assertTrue(any(c["name"] == "tests" and c["status"] == "skipped" for c in receipt["checks"]))

    def test_timeout_stops_the_entire_descendant_process_tree(self):
        child = ("import pathlib,time\np=pathlib.Path('.gate/heartbeat')\n"
                 "p.parent.mkdir(exist_ok=True)\n"
                 "for i in range(60):\n p.write_text(str(i))\n time.sleep(0.1)\n")
        parent = ("import subprocess,sys,time\nsubprocess.Popen([sys.executable, '-c', "
                  + repr(child) + "])\ntime.sleep(6)\n")
        root = self.project({"spawn.py": parent}, {
            "typeCheckCommand": [sys.executable, "spawn.py"], "testQueue": {"timeoutSeconds": 1},
        })
        self.write(root, "changed.py", "value = 1\n")
        started = time.monotonic()
        result, receipt = self.check(root)
        self.assertNotEqual(result.returncode, 0)
        marker = root / ".gate/heartbeat"
        self.assertTrue(marker.is_file(), result.stdout + result.stderr)
        before = marker.read_text()
        time.sleep(0.35)
        self.assertEqual(marker.read_text(), before, "grandchild survived command timeout")
        self.assertLess(time.monotonic() - started, 4.0, "timeout waited for the surviving grandchild")
        self.assertTrue(any(c["name"] == "type-check" and "timed out" in c.get("reason", "")
                            for c in receipt["checks"]))


if __name__ == "__main__":
    unittest.main()
