import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-11-16T10:00:00Z"


def load_tool(name, folder="tools"):
    path = ROOT / folder / (name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def jsonl(self, name, rows):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def claude(self, name="claude/main.jsonl", model="model-x"):
        message = {"id": "reply-" + model, "model": model, "usage": {"input_tokens": 100,
            "cache_creation": {"ephemeral_5m_input_tokens": 20, "ephemeral_1h_input_tokens": 10},
            "cache_read_input_tokens": 1000, "output_tokens": 40}, "content": [
                {"type": "tool_use", "id": "read-" + model, "name": "Read", "input": {"limit": 5}},
                {"type": "tool_use", "id": "edit-" + model, "name": "Edit", "input": {"file_path": "a.py", "new_string": "abc"}}]}
        row = {"type": "assistant", "timestamp": STAMP, "message": message}
        return self.jsonl(name, [row, row])

    def test_claude_cache_tiers_dedup_tools_and_subagents(self):
        self.claude()
        self.claude("claude/main/subagents/sub.jsonl", "deepseek-x")
        module = load_tool("sessions", "tools/lib")
        steps, tools = [], []
        result = module.walk("claude", roots=[str(self.root / "claude")], on_step=steps.append, on_tool=tools.append)
        self.assertEqual((result["steps"], len(tools)), (2, 4))
        self.assertEqual(steps[0]["u"], {"fresh": 130, "freshPlain": 100, "cacheW5": 20,
            "cacheW1h": 10, "cacheRead": 1000, "output": 40, "ctx": 1130})
        self.assertEqual(sum(step["sub"] for step in steps), 1)
        self.assertEqual(sum(tool["codeChars"] for tool in tools), 6)

    def test_codex_prefers_response_records_and_deduplicates_archive(self):
        rows = [{"type": "session_meta", "timestamp": STAMP, "payload": {"id": "session", "parent_thread_id": "parent"}},
                {"type": "turn_context", "timestamp": STAMP, "payload": {"model": "gpt-x"}},
                {"type": "event_msg", "timestamp": STAMP, "payload": {"type": "token_count", "info": {"last_token_usage": {"input_tokens": 999}}}},
                {"type": "token_usage_record", "timestamp": STAMP, "payload": {"response_id": "r1", "usage": {"input_tokens": 1000, "cached_input_tokens": 700, "cache_write_input_tokens": 50, "output_tokens": 100, "reasoning_output_tokens": 40}}}]
        self.jsonl("codex/current/rollout.jsonl", rows)
        self.jsonl("codex/archive/rollout.jsonl", rows)
        steps = []
        result = load_tool("sessions", "tools/lib").walk("codex", roots=[str(self.root / "codex")], on_step=steps.append)
        self.assertEqual((result["files"], len(steps)), (1, 1))
        self.assertEqual((steps[0]["u"]["fresh"], steps[0]["u"]["freshPlain"], steps[0]["u"]["output"]), (300, 250, 100))
        self.assertTrue(steps[0]["sub"])

    def test_legacy_codex_ignores_repeated_totals(self):
        event = {"type": "event_msg", "timestamp": STAMP, "payload": {"type": "token_count", "info": {
            "last_token_usage": {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 10},
            "total_token_usage": {"total_tokens": 110}}}}
        self.jsonl("old/rollout.jsonl", [event, event])
        steps = []
        load_tool("sessions", "tools/lib").walk("codex", roots=[str(self.root / "old")], on_step=steps.append)
        self.assertEqual(len(steps), 1)

    def test_gemini_counts_cached_input_and_thought_output(self):
        chats = self.root / "gemini/project/chats"
        chats.mkdir(parents=True)
        data = {"sessionId": "g1", "messages": [{"id": "m1", "type": "gemini", "timestamp": STAMP,
            "model": "gemini-x", "tokens": {"input": 500, "cached": 300, "output": 20, "thoughts": 10},
            "toolCalls": [{"id": "write", "name": "write_file", "args": {"file_path": "x.py", "content": "print(1)"}}]}]}
        (chats / "session.json").write_text(json.dumps(data), encoding="utf-8")
        steps, tools = [], []
        load_tool("sessions", "tools/lib").walk("gemini", roots=[str(self.root / "gemini")], on_step=steps.append, on_tool=tools.append)
        self.assertEqual((steps[0]["u"]["fresh"], steps[0]["u"]["output"], tools[0]["codeChars"]), (200, 30, 8))

    def config(self, section, value):
        (self.root / "gate.config.json").write_text(json.dumps({section: value}), encoding="utf-8")

    def run_tool(self, name, *arguments):
        return subprocess.run([sys.executable, str(ROOT / "tools" / (name + ".py"))] + list(arguments),
                              cwd=self.root, text=True, capture_output=True, check=False, timeout=10, shell=False)

    def test_usage_cli_reads_config_prices_and_roots_without_changing_logs(self):
        path = self.claude()
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.config("tokenUsage", {"agent": "claude", "sessionRoots": {"claude": ["claude"]},
            "prices": [["model-x", [2, 10]], [".", [4, 20]]], "cacheReadPrice": 0.5, "days": 7})
        result = self.run_tool("token-usage", "--json", "--now", "2026-11-16T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)["claude"]
        self.assertEqual(data["total"]["replies"], 1)
        self.assertEqual(data["total"]["fresh"], 130)
        self.assertAlmostEqual(data["total"]["usd"], 0.00119)
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_stages_reports_core_metrics_and_only_writes_requested_report(self):
        path = self.claude()
        self.config("stages", {"agent": "claude", "sessionRoots": {"claude": ["claude"]},
            "prices": [[".", [2, 10]]], "cacheReadPrice": 0.5, "activeHourMinUSD": 0.001,
            "bigContextTokens": 1000, "stages": [{"key": "s1", "name": "baseline", "from": "2026-11-16T00:00:00Z", "to": "2026-11-17T00:00:00Z"}]})
        report = self.root / "report.json"
        result = self.run_tool("stages", "--now", "2026-11-16T12:00:00Z", "--out", str(report))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(report.read_text(encoding="utf-8"))["stages"]["s1"]
        self.assertEqual((data["steps"], data["sessions"], data["wholeFileReadPct"], data["bigContextPct"]), (2, 1, 0, 100))
        self.assertEqual(data["activeHours"], 1)
        self.assertEqual(data["codeChars"], 3)
        self.assertAlmostEqual(data["costUSD"], 0.00119)
        self.assertTrue(path.exists())

    def test_empty_roots_do_not_scan_user_home(self):
        self.config("tokenUsage", {"sessionRoots": {"claude": []}})
        result = self.run_tool("token-usage", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["claude"]["files"], 0)

    def test_unconfigured_prices_leave_tokens_available_and_usd_unknown(self):
        self.claude()
        roots = {"claude": ["claude"]}
        self.config("tokenUsage", {"sessionRoots": roots})
        usage = self.run_tool("token-usage", "--json", "--now", "2026-11-16T12:00:00Z")
        self.assertEqual(usage.returncode, 0, usage.stderr)
        total = json.loads(usage.stdout)["claude"]["total"]
        self.assertEqual((total["fresh"], total["unpricedReplies"]), (130, 1))
        self.assertIsNone(total["usd"])
        self.config("stages", {"sessionRoots": roots, "stages": [
            {"key": "one", "from": "2026-11-16T00:00:00Z", "to": "2026-11-17T00:00:00Z"}]})
        stage = self.run_tool("stages", "--json", "--now", "2026-11-16T12:00:00Z")
        self.assertEqual(stage.returncode, 0, stage.stderr)
        row = json.loads(stage.stdout)["stages"]["one"]
        self.assertEqual(row["steps"], 2)
        self.assertIsNone(row["costUSD"])
        self.assertIsNone(row["activeHours"])

    def test_stages_preserve_long_tests_subagent_cost_and_deliveries(self):
        path = self.claude()
        self.claude("claude/main/subagents/sub.jsonl", "model-sub")
        extra = [{"type": "assistant", "timestamp": "2026-11-16T10:01:00Z", "message": {"content": [
            {"type": "tool_use", "id": "test-one", "name": "Bash", "input": {"command": "python -m unittest tests.one"}}]}},
            {"type": "user", "timestamp": "2026-11-16T10:12:00Z", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "test-one", "content": "OK"}]}}]
        with path.open("a", encoding="utf-8") as stream:
            for row in extra:
                stream.write(json.dumps(row) + "\n")
        before = {str(file): hashlib.sha256(file.read_bytes()).hexdigest() for file in (self.root / "claude").rglob("*.jsonl")}
        deliveries = self.root / "deliveries"
        deliveries.mkdir()
        (deliveries / "2026-11-16-proof.txt").write_text("proof", encoding="utf-8")
        self.config("stages", {"sessionRoots": {"claude": ["claude"]}, "prices": [[".", [2, 10]]],
            "cacheReadPrice": 0.5, "activeHourMinUSD": 0.001, "stages": [
                {"key": "one", "from": "2026-11-16T00:00:00Z", "to": "2026-11-17T00:00:00Z"}]})
        result = self.run_tool("stages", "--json", "--deliveries", "deliveries", "--now", "2026-11-17T00:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["stages"]["one"]
        self.assertEqual((row["steps"], row["foregroundTests"], row["testsOver10minPct"], row["deliveries"]), (5, 1, 100, 1))
        self.assertEqual((row["subagentCostPct"], row["activeHours"], row["codeChars"]), (50, 1, 6))
        self.assertAlmostEqual(row["costUSD"], 0.00238)
        self.assertEqual(before, {str(file): hashlib.sha256(file.read_bytes()).hexdigest() for file in (self.root / "claude").rglob("*.jsonl")})


if __name__ == "__main__":
    unittest.main()
