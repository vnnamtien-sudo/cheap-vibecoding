"""Real Git integration for the optional pre-commit setup."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tools/install-hook.py"


class HookInstallTests(unittest.TestCase):
    def project(self, directory):
        root = Path(directory)
        subprocess.run(["git", "init", "--quiet", str(root)], check=True)
        config = {"maxFileLines": 400, "maxFunctionLines": 80, "readLimitLines": 60,
                  "bannedPatterns": [{"pattern": "FORBIDDEN_SAMPLE", "description": "fixture rule"}],
                  "layers": [], "testCommand": [], "typeCheckCommand": [], "dataCheckCommand": []}
        (root / "gate.config.json").write_text(json.dumps(config), encoding="utf-8")
        return root

    def run_install(self, root):
        return subprocess.run([sys.executable, str(INSTALL), "--root", str(root)],
                              capture_output=True, text=True)

    def test_preserves_existing_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(directory)
            hook = root / ".git/hooks/pre-commit"
            hook.write_text("existing", encoding="utf-8")
            result = self.run_install(root)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(hook.read_text(encoding="utf-8"), "existing")

    def test_installed_hook_blocks_staged_content(self):
        with tempfile.TemporaryDirectory(prefix="gate with spaces ") as directory:
            root = self.project(directory)
            result = self.run_install(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            (root / "sample.txt").write_text("FORBIDDEN_SAMPLE", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "sample.txt", "gate.config.json"], check=True)
            hook = root / ".git/hooks/pre-commit"
            result = subprocess.run(
                ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@noreply.invalid",
                 "commit", "--quiet", "-m", "blocked fixture"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            receipt = json.loads((root / ".gate/self-check.json").read_text(encoding="utf-8"))
            self.assertFalse(receipt["ok"])
            violations = [item for check in receipt["checks"] for item in check.get("violations", [])]
            self.assertTrue(any(item["file"] == "sample.txt" and item["rule"] == "banned-pattern"
                                for item in violations), receipt)
            if os.name != "nt":
                self.assertTrue(os.access(hook, os.X_OK))


if __name__ == "__main__":
    unittest.main()
