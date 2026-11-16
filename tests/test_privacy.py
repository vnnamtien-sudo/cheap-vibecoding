import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("privacy", Path(__file__).resolve().parents[1] / "tools/privacy-scan.py")
privacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(privacy)


class PrivacyTests(unittest.TestCase):
    def findings(self, content, name="sample.txt"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return privacy.scan(root, [name])

    def test_redacts_secrets_in_results(self):
        value = "sk" + "-" + "sensitive" * 4
        hits = self.findings(value)
        self.assertEqual(hits[0]["rule"], "credential")
        self.assertNotIn(value, str(hits))

    def test_paths_language_and_disallowed_terms(self):
        samples = [("Q" + ":/home", "absolute-drive-path"),
                   ("multi" + "-account", "account-cycling"),
                   ("f" * 40, "long-hex")]
        for content, rule in samples:
            with self.subTest(rule=rule):
                self.assertEqual(self.findings(content)[0]["rule"], rule)

    def test_email_exception_and_repository_identity(self):
        self.assertEqual(self.findings("bot@noreply.invalid"), [])
        self.assertEqual(self.findings("https://github.com/vnnamtien-sudo/cheap-vibecoding"), [])
        self.assertEqual(self.findings("person" + "@example.invalid")[0]["rule"], "email")
        self.assertEqual(self.findings("notnoreply" + "@example.invalid")[0]["rule"], "email")

    def test_optional_framework_example_only(self):
        framework = "Djan" + "go"
        self.assertEqual(self.findings(framework, "examples/optional.json"), [])
        self.assertEqual(self.findings(framework, "src/main.py")[0]["rule"], "fixed-framework")

    def test_capacity_evasion_language_is_blocked(self):
        for phrase in ["rotating" + " accounts", "multiple" + " accounts", "switching" + " accounts"]:
            self.assertEqual(self.findings(phrase)[0]["rule"], "account-cycling")

    def test_unreadable_artifacts_require_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "blob.bin").write_bytes(b"a\0b")
            self.assertEqual(privacy.scan(root, ["blob.bin"])[0]["rule"], "binary-review-required")

    def test_accented_text_and_custom_private_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "text.txt").write_text("c\u00f3", encoding="utf-8")
            self.assertEqual(privacy.scan(root, ["text.txt"]), [])
            (root / ".gate").mkdir()
            (root / ".gate" / "private-patterns.json").write_text(json.dumps([{"description": "local-term", "pattern": "Secret" + "Name"}]), encoding="utf-8")
            local = privacy.load_patterns(root, {"privacy": {"patterns": [{"description": "cfg", "pattern": "x"}]}})
            self.assertEqual([p["description"] for p in local], ["cfg", "local-term"])
            (root / "text.txt").write_text("PrivateProject", encoding="utf-8")
            extra = [{"description": "private-project", "pattern": "PrivateProject"}]
            self.assertEqual(privacy.scan(root, ["text.txt"], extra)[0]["rule"], "private-project")


if __name__ == "__main__":
    unittest.main()
