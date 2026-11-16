"""Initialization must inspect projects without executing their code."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "init.py"
MAPPER = REPO / "tools" / "targeted-tests.py"
WORK = REPO / ".work" / "python-core-tests"


class InitTests(unittest.TestCase):
    def project(self, files):
        WORK.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="init-", dir=str(WORK))
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, content in files.items():
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content, encoding="utf-8")
        return root

    def run_init(self, root, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=root,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False, timeout=15)

    @staticmethod
    def config(root):
        return json.loads((root / "gate.config.json").read_text(encoding="utf-8"))

    def test_scan_identifies_languages_frameworks_layers_without_execution(self):
        root = self.project({
            "package.json": json.dumps({"scripts": {"test": "node --test"}}),
            "package-lock.json": "{}", "src/api/health.js": "throw new Error('do not run');",
            "src/services/health.ts": "export const health: string = 'ok';",
            "tests/health.test.cjs": "throw new Error('do not run');",
        })
        result = self.run_init(root, "--root", str(root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        draft = self.config(root)
        self.assertEqual(draft["detected"]["languages"], ["JavaScript", "TypeScript"])
        self.assertEqual(draft["detected"]["packageManagers"], ["npm"])
        self.assertEqual(draft["detected"]["testFrameworks"], ["Node.js test runner"])
        self.assertTrue({"src/api", "src/services"}.issubset({layer["path"] for layer in draft["layers"]}))
        self.assertTrue(all(isinstance(layer["allow"], list) for layer in draft["layers"]))
        self.assertEqual([draft[k] for k in ("maxFileLines", "maxFunctionLines", "readLimitLines")], [400, 80, 60])
        self.assertTrue(draft["review"])

    @unittest.skipUnless(shutil.which("node"), "Project Node.js test runtime is not installed")
    def test_generated_node_mapping_runs_related_tests_only_and_rejects_unmapped(self):
        root = self.project({
            "package.json": json.dumps({"scripts": {"test": "node --test"}}),
            "src/sum.js": "throw new Error('source is not a test');",
            "src/other.js": "module.exports = 1;",
            "tests/sum.test.cjs": "require('node:fs').writeFileSync('sum-ran', 'yes');",
            "tests/other.test.cjs": "require('node:fs').writeFileSync('other-ran', 'yes');",
        })
        result = self.run_init(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        command = self.config(root)["testCommand"]
        self.assertEqual(command[1:], [".ai-gates/targeted-tests.py", "{files}"])
        executed = subprocess.run([sys.executable, command[1], "src/sum.js"], cwd=root,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertEqual(executed.returncode, 0, repr(executed))
        self.assertEqual((root / "sum-ran").read_text(), "yes")
        self.assertFalse((root / "other-ran").exists())
        absent = subprocess.run([sys.executable, command[1], "src/unmapped.js"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertNotEqual(absent.returncode, 0)
        self.assertIn("noMapping", absent.stdout + absent.stderr)

    def test_python_runner_executes_only_the_concrete_related_unittest(self):
        test = ("import pathlib, unittest\nclass Sample(unittest.TestCase):\n"
                "    def test_value(self):\n        pathlib.Path({!r}).write_text('yes')\n        self.assertEqual(2 + 2, 4)\n")
        root = self.project({"src/sum.py": "value = 4\n", "src/other.py": "value = 1\n",
                             "tests/__init__.py": "", "tests/test_sum.py": test.format("sum-ran"),
                             "tests/test_other.py": test.format("other-ran")})
        self.assertEqual(self.run_init(root).returncode, 0)
        result = subprocess.run([sys.executable, str(root / ".ai-gates/targeted-tests.py"), "src/sum.py"],
                                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((root / "sum-ran").is_file())
        self.assertFalse((root / "other-ran").exists())

    def test_code_without_tests_reports_no_mapping_after_initialization(self):
        root = self.project({"src/value.py": "value = 1\n"})
        self.assertEqual(self.run_init(root).returncode, 0)
        helper = root / ".ai-gates/targeted-tests.py"
        result = subprocess.run([sys.executable, str(helper), "src/value.py"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["noMapping"], ["src/value.py"])

    def test_empty_unittest_module_is_not_a_successful_test_run(self):
        root = self.project({"src/value.py": "value = 1\n", "tests/__init__.py": "",
                             "tests/test_value.py": "import unittest\n",
                             "unittest.py": "print('Ran 0 tests in 0.000s')\n"})
        self.assertEqual(self.run_init(root).returncode, 0)
        result = subprocess.run([sys.executable, str(root / ".ai-gates/targeted-tests.py"), "src/value.py"], cwd=root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no tests ran", result.stdout + result.stderr)

    def test_python_unittest_mapping_supports_hyphens_and_shared_libraries(self):
        root = self.project({
            "tools/lib/common.py": "VALUE = 1\n", "tools/self-check.py": "from lib.common import VALUE\n",
            "tools/init.py": "from lib.common import VALUE\n", "tools/other.py": "VALUE = 2\n",
            "tests/__init__.py": "", "tests/test_self_check.py": "import unittest\n",
            "tests/test_init.py": "import unittest\n", "tests/test_other.py": "import unittest\n",
        })
        result = self.run_init(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config(root)["detected"]["testFrameworks"], ["unittest"])
        runner = root / ".ai-gates/targeted-tests.py"
        plan = subprocess.run([sys.executable, str(runner), "--plan", "tools/lib/common.py"], cwd=root,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        receipt = json.loads(plan.stdout)
        self.assertEqual(receipt["tests"], ["tests/test_init.py", "tests/test_self_check.py"])
        self.assertEqual(receipt["commands"][0][1:], ["-m", "unittest", "tests.test_init", "tests.test_self_check"])

    def test_vitest_and_pytest_remain_reviewable_without_invented_commands(self):
        cases = [({
            "package.json": json.dumps({"packageManager": "pnpm@9.0.0", "devDependencies": {"vitest": "*"}}),
            "pnpm-lock.yaml": "", "src/index.ts": "export const value = 1;",
        }, "Vitest"), ({
            "pyproject.toml": '[project]\nname = "sample"\n[tool.pytest.ini_options]\n',
            "src/sample.py": "def value():\n    return 1\n", "tests/test_sample.py": "def test_value():\n    assert True\n",
        }, "pytest")]
        for files, framework in cases:
            with self.subTest(framework=framework):
                root = self.project(files)
                result = self.run_init(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                draft = self.config(root)
                self.assertEqual(draft["detected"]["testFrameworks"], [framework])
                self.assertEqual(draft["testCommand"], ["{python}", ".ai-gates/targeted-tests.py", "{files}"])
                self.assertEqual(draft["typeCheckCommand"], [])
                self.assertEqual(draft["dataCheckCommand"], [])
                self.assertTrue((root / ".ai-gates/targeted-tests.py").exists())
                self.assertIn("testCommand", " ".join(draft["review"]))

    def test_unknown_project_returns_explicit_draft(self):
        root = self.project({"README.md": "An unknown project."})
        result = self.run_init(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        draft = self.config(root)
        self.assertEqual(draft["detected"]["languages"], [])
        self.assertEqual(draft["testCommand"], [])
        self.assertIn("unknown", " ".join(draft["review"]).lower())

    def test_existing_configuration_is_preserved_unless_force_is_explicit(self):
        original = '{ "custom": true }\n'
        root = self.project({"gate.config.json": original, "src/app.js": ""})
        self.assertEqual(self.run_init(root).returncode, 0)
        self.assertEqual((root / "gate.config.json").read_text(), original)
        self.assertFalse((root / ".gate").exists())
        self.assertEqual(self.run_init(root, "--force").returncode, 0)
        self.assertEqual(self.config(root)["detected"]["languages"], ["JavaScript"])

    def test_ignored_generated_dependency_and_linked_trees_do_not_influence_detection(self):
        root = self.project({"src/app.js": "", "node_modules/demo/package.json": "{bad",
                             "node_modules/demo/hide.py": "", ".venv/lib/hide.py": "",
                             "vendor/hide.rs": "", "dist/generated.go": "", ".git/cache.java": "",
                             ".gate/old-generated.ts": "", ".work/old-generated.rb": ""})
        outside = self.project({"only-python.py": ""})
        try:
            (root / "linked").symlink_to(outside, target_is_directory=True)
        except OSError:
            pass
        result = self.run_init(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        draft = self.config(root)
        self.assertEqual(draft["detected"]["languages"], ["JavaScript"])
        self.assertEqual(draft["detected"]["packageManagers"], [])

    def test_malformed_manifest_is_review_item_and_bad_root_writes_nothing(self):
        root = self.project({"package.json": "{bad", "main.js": ""})
        result = self.run_init(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("package.json", " ".join(self.config(root)["review"]))
        self.assertNotEqual(self.run_init(root, "--root").returncode, 0)
        absent = root / "absent"
        self.assertNotEqual(self.run_init(root, "--root", str(absent)).returncode, 0)
        self.assertFalse(absent.exists())

    def test_mapper_rejects_path_escape_and_does_not_claim_docs_are_tests(self):
        root = self.project({"tests/test_sum.py": "import unittest\n", "src/sum.py": "value = 1\n"})
        for changed in ("../tests/test_sum.py", "--test", str(root / "tests/test_sum.py")):
            with self.subTest(changed=changed):
                result = subprocess.run([sys.executable, str(MAPPER), "--plan", changed], cwd=root,
                                        capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
                self.assertNotEqual(result.returncode, 0)
        skipped = subprocess.run([sys.executable, str(MAPPER), "--plan", "README.md"], cwd=root,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertEqual(skipped.returncode, 0)
        self.assertEqual(json.loads(skipped.stdout)["status"], "skipped")

    def test_explicit_test_mappings_cover_responsibility_names_and_directory_consumers(self):
        root = self.project({
            "tools/check-private.py": "value = 1\n", "tools/lib/shared.py": "value = 1\n",
            "tests/test_privacy.py": "import unittest\n", "tests/test_hooks.py": "import unittest\n",
            "gate.config.json": json.dumps({"testMappings": {
                "tools/check-private.py": ["tests/test_privacy.py"],
                "tools/lib/": ["tests/test_hooks.py"], "tools/lib/shared.py": ["tests/test_privacy.py"],
            }}),
        })
        result = subprocess.run([sys.executable, str(MAPPER), "--plan", "tools/check-private.py", "tools/lib/shared.py"],
                                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["mappings"]["tools/check-private.py"], ["tests/test_privacy.py"])
        self.assertEqual(plan["mappings"]["tools/lib/shared.py"], ["tests/test_hooks.py", "tests/test_privacy.py"])


if __name__ == "__main__":
    unittest.main()
