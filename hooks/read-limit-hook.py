#!/usr/bin/env python3
"""Bound Claude reads using the target project's gate.config.json."""
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hooks.lib.agent_io import run_hook
from tools.lib.gate_config import load_config


def count_lines(file, cap):
    try:
        path = Path(file)
        if not path.is_file():
            return None
        count, last = 0, b"\n"
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                if b"\0" in chunk:
                    return None
                count += chunk.count(b"\n")
                last = chunk[-1:]
                if count > cap:
                    return {"lines": count, "over": True}
        count += int(last != b"\n")
        return {"lines": count, "over": count > cap}
    except OSError:
        return None


def decide(value, config_path=None):
    try:
        root = Path(value.get("cwd") or Path.cwd())
        config = load_config(root, config_path=config_path)
        if config.get("readLimit", {}).get("enabled", True) is False:
            return None
        maximum = config["readLimitLines"]
        args = value.get("tool_input", {})
        reason = "Read limit: %s lines. Search for the target, then read a bounded range." % maximum
        if value.get("tool_name") == "Read":
            if args.get("limit") is not None:
                limit = args["limit"]
                try:
                    number = float(limit)
                except (TypeError, ValueError):
                    return reason
                return None if not isinstance(limit, bool) and math.isfinite(number) and number.is_integer() and 0 < number <= maximum else reason
            result = count_lines(root / args.get("file_path", ""), maximum)
            return reason if result and result["over"] else None
        if value.get("tool_name") in ("Shell", "Bash"):
            # shortcut: literal cat dumps only; shell parsing is deliberately out of scope.
            match = re.fullmatch(r'''\s*cat\s+(?:"([^"]+)"|'([^']+)'|([^\s|;&>]+))\s*''', args.get("command", ""))
            if match:
                result = count_lines(root / next(part for part in match.groups() if part), maximum)
                if result and result["over"]:
                    return reason
        return None
    except Exception as error:
        return "Invalid gate configuration: " + str(error)


if __name__ == "__main__":
    sys.exit(run_hook(decide))
