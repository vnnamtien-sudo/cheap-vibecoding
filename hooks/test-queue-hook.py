#!/usr/bin/env python3
"""Optional, gentle reminder to run recognized tests through the Python queue."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hooks.lib.agent_io import run_hook
from tools.lib.gate_config import load_config


def decide(value, config_path=None):
    try:
        config = load_config(value.get("cwd") or Path.cwd(), config_path=config_path)
        queue = config.get("testQueue", {})
        if not queue.get("hookEnabled", False) or value.get("tool_name") not in ("Bash", "Shell"):
            return None
        template = config.get("testCommand", [])
        signature = " ".join(str(part) for part in template if part not in ("{files}", "{python}")) if isinstance(template, list) else str(template).replace("{files}", "").strip()
        patterns = queue.get("testPatterns", [r'''\bpython(?:3(?:\.\d+)?)?(?:\.exe)?["']?\s+-m\s+(?:unittest|pytest)\b''', r"\bpytest\b", r"\bnode\s+--test\b", r"\bnpm\s+(?:run\s+)?test\b"])
        for segment in re.split(r"&&|\|\||[;\n]", str(value.get("tool_input", {}).get("command", ""))):
            if re.search(r'''(?:[/\\]|\b)test-queue\.py["']?\s+run\b''', segment):
                continue
            if re.search(r'''(?:[/\\]|\b)self-check\.py["']?(?:\s|$)''', segment):
                continue
            if (signature and signature in segment) or any(re.search(pattern, segment) for pattern in patterns):
                return "Run targeted tests through the queue: python tools/test-queue.py run --label unit -- <command arguments>."
        return None
    except Exception as error:
        return "Invalid gate configuration: " + str(error)


if __name__ == "__main__":
    sys.exit(run_hook(decide))
