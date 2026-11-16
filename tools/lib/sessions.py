"""Read local Claude/DeepSeek, Codex and Gemini session logs without modifying them."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re

AGENTS = ("claude", "codex", "gemini", "deepseek")
CODE = re.compile(r"\.(?:c?js|mjs|ts|tsx|jsx|py|ps1|cmd|bat|sql|css|vue|sh|go|rs|java|kt|rb|php|cs)$", re.I)
PART_READ = re.compile(r"sed -n|head -n|head -\d|tail -n|tail -\d|-TotalCount|-Tail\b|Select-Object -(?:First|Skip|Last)|\bnl -ba\b.*\|")
ALL_READ = re.compile(r"(?:^|[\s;&|(])(?:cat|type|Get-Content|gc)\s+[^|>]")


def timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) else None
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp() * 1000
    except (ValueError, OverflowError):
        return None


def home(value):
    return Path(os.path.expanduser(str(value)))


def session_roots(config, agent, root, overrides=None):
    values = overrides if overrides else config.get("sessionRoots", {}).get(agent, [])
    if isinstance(values, str):
        values = [values]
    roots = []
    for value in values:
        for item in str(value).split(","):
            if item.strip():
                path = home(item.strip())
                roots.append(str(path if path.is_absolute() else Path(root) / path))
    return roots


def files_of(agent, roots, since=0):
    extension = ".json" if agent == "gemini" else ".jsonl"
    result, seen = [], set()
    for root in roots:
        path = home(root)
        candidates = [path] if path.is_file() else sorted(path.rglob("*")) if path.is_dir() else []
        for file in candidates:
            try:
                if not file.is_file() or file.suffix != extension or (since and file.stat().st_mtime * 1000 < since):
                    continue
            except OSError:
                continue
            if agent == "gemini" and "chats" not in file.parts:
                continue
            identity = file.name if agent == "codex" else str(file.resolve())
            if identity in seen:
                continue
            seen.add(identity)
            result.append(file)
    return result


def shell_read(command):
    return "part" if PART_READ.search(command) else "all" if ALL_READ.search(command) else None


def patch_chars(text):
    count, code = 0, False
    for line in str(text).splitlines():
        match = re.match(r"\*\*\* (?:Add|Update) File: (.+)$", line.strip())
        if match:
            code = bool(CODE.search(match.group(1)))
        elif line.startswith("*** "):
            code = False
        elif code and line.startswith("+") and not line.startswith("+++"):
            count += len(line) - 1
    return count


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return max(0, value)
    return 0


def _json_rows(file):
    with file.open("r", encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(row, dict):
                yield row


def read_claude(file, on_step, on_tool):
    sub = "subagents" in file.parts
    run_id = str(file) if sub else file.stem
    sid = file.parent.parent.name if sub else run_id
    for row in _json_rows(file):
        time = timestamp(row.get("timestamp"))
        if time is None:
            continue
        message = row.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if row.get("type") == "assistant" and isinstance(usage, dict) and message.get("id"):
            creation = usage.get("cache_creation") or {}
            w5 = _number(creation.get("ephemeral_5m_input_tokens", usage.get("cache_creation_input_tokens", 0)))
            w1 = _number(creation.get("ephemeral_1h_input_tokens", 0))
            plain, cached = _number(usage.get("input_tokens")), _number(usage.get("cache_read_input_tokens"))
            on_step({"t": time, "key": message["id"], "model": message.get("model") or "?", "sid": sid,
                     "runId": run_id, "sub": sub or row.get("isSidechain") is True,
                     "u": {"fresh": plain + w5 + w1, "freshPlain": plain, "cacheW5": w5, "cacheW1h": w1,
                           "cacheRead": cached, "output": _number(usage.get("output_tokens")), "ctx": plain + w5 + w1 + cached}})
        for block in message.get("content", []) if isinstance(message.get("content"), list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result" and block.get("tool_use_id"):
                on_tool({"t": time, "id": block["tool_use_id"], "done": time})
            if block.get("type") != "tool_use" or not block.get("id"):
                continue
            args, name, chars = block.get("input") or {}, block.get("name"), 0
            if CODE.search(str(args.get("file_path", ""))):
                if name == "Edit":
                    chars = len(str(args.get("new_string", "")))
                elif name == "Write":
                    chars = len(str(args.get("content", "")))
                elif name == "MultiEdit":
                    chars = sum(len(str(edit.get("new_string", ""))) for edit in args.get("edits", []))
            command = str(args.get("command", "")) if name in ("Bash", "PowerShell", "Shell") else None
            on_tool({"t": time, "id": block["id"], "read": ("part" if args.get("limit") else "all") if name == "Read" else shell_read(command) if command else None,
                     "shell": command, "bg": bool(args.get("run_in_background")), "codeChars": chars})


def _is_usage_record(row):
    return row.get("type") == "token_usage_record" or (row.get("payload") or {}).get("type") == "token_usage_record"


def read_codex(file, on_step, on_tool):
    has_record = any(_is_usage_record(row) for row in _json_rows(file))
    run_id, model, sub, previous_total, count = file.stem, "?", False, None, 0
    sid = run_id
    for row in _json_rows(file):
        time, payload = timestamp(row.get("timestamp")), row.get("payload") or {}
        if time is None or not isinstance(payload, dict):
            continue
        if row.get("type") == "session_meta":
            sid = payload.get("session_id") or payload.get("id") or sid
            sub = bool(payload.get("parent_thread_id") or (isinstance(payload.get("source"), dict) and payload["source"].get("subagent")))
            continue
        if row.get("type") == "turn_context":
            model = payload.get("model") or model
            continue
        usage, key = None, None
        if has_record and _is_usage_record(row) and isinstance(payload.get("usage"), dict):
            usage, key = payload["usage"], payload.get("response_id") or "%s#%s" % (run_id, count)
        elif not has_record and payload.get("type") == "token_count":
            info = payload.get("info") or {}
            if isinstance(info.get("last_token_usage"), dict):
                total = (info.get("total_token_usage") or {}).get("total_tokens")
                if total is not None and total == previous_total:
                    continue
                previous_total = total
                usage, key = info["last_token_usage"], "%s#%s" % (run_id, count)
        if usage is not None:
            count += 1
            plain, cached, written = _number(usage.get("input_tokens")), _number(usage.get("cached_input_tokens")), _number(usage.get("cache_write_input_tokens"))
            on_step({"t": time, "key": key, "model": payload.get("model") or model, "sid": sid, "runId": run_id, "sub": sub,
                     "u": {"fresh": max(0, plain - cached), "freshPlain": max(0, plain - cached - written), "cacheW5": written,
                           "cacheW1h": 0, "cacheRead": cached, "output": _number(usage.get("output_tokens")), "ctx": plain}})
            continue
        if row.get("type") != "response_item":
            continue
        identity, kind = payload.get("call_id") or payload.get("id"), payload.get("type")
        if not identity:
            continue
        if kind in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
            on_tool({"t": time, "id": identity, "done": time})
            continue
        text = None
        if kind == "function_call":
            try:
                args = json.loads(payload.get("arguments") or "{}")
            except (ValueError, TypeError):
                args = {}
            command = args.get("command", args.get("cmd")) if isinstance(args, dict) else None
            text = " ".join(str(part) for part in command) if isinstance(command, list) else str(command) if command is not None else str(payload.get("arguments") or "")
        elif kind == "custom_tool_call":
            text = str(payload.get("input") or "")
        elif kind == "local_shell_call":
            command = (payload.get("action") or {}).get("command", "")
            text = " ".join(str(part) for part in command) if isinstance(command, list) else str(command)
        if text is not None:
            patch = "*** Begin Patch" in text
            on_tool({"t": time, "id": identity, "read": None if patch else shell_read(text), "shell": None if patch else text,
                     "bg": False, "codeChars": patch_chars(text) if patch else 0})


def read_gemini(file, on_step, on_tool):
    with file.open("r", encoding="utf-8-sig") as stream:
        data = json.load(stream)
    sid, run_id = data.get("sessionId") or file.stem, file.stem
    for index, message in enumerate(data.get("messages", [])):
        time = timestamp(message.get("timestamp") or data.get("lastUpdated"))
        if time is None:
            continue
        usage = message.get("tokens")
        if isinstance(usage, dict) and message.get("type") in ("gemini", "model"):
            plain, cached = _number(usage.get("input")), _number(usage.get("cached"))
            on_step({"t": time, "key": "%s#%s" % (sid, message.get("id", index)), "model": message.get("model") or "?",
                     "sid": sid, "runId": run_id, "sub": False, "u": {"fresh": max(0, plain - cached), "freshPlain": max(0, plain - cached),
                     "cacheW5": 0, "cacheW1h": 0, "cacheRead": cached, "output": _number(usage.get("output")) + _number(usage.get("thoughts")), "ctx": plain}})
        for call in message.get("toolCalls", []):
            args, name = call.get("args") or {}, str(call.get("name") or "")
            read, command, chars = None, None, 0
            if name == "read_file":
                read = "part" if args.get("limit") or args.get("end_line") else "all"
            elif name == "read_many_files":
                read = "all"
            elif name == "run_shell_command":
                command = str(args.get("command") or "")
                read = shell_read(command)
            elif name in ("write_file", "replace") and CODE.search(str(args.get("file_path") or "")):
                chars = len(str(args.get("content", args.get("new_string", ""))))
            on_tool({"t": timestamp(call.get("timestamp")) or time, "id": call.get("id") or "%s#%s#%s" % (sid, index, name),
                     "read": read, "shell": command, "bg": False, "codeChars": chars})


def walk(agent, roots=None, since=0, on_step=None, on_tool=None):
    readers = {"claude": read_claude, "deepseek": read_claude, "codex": read_codex, "gemini": read_gemini}
    if agent not in readers:
        raise ValueError("Unknown agent %s; choose %s" % (agent, ", ".join(AGENTS)))
    seen, seen_tools, warnings = set(), set(), []
    files = files_of(agent, roots or [], since)

    def step(value):
        if value["key"] not in seen:
            seen.add(value["key"])
            if on_step:
                on_step(value)

    def tool(value):
        if value.get("done") is not None:
            if on_tool:
                on_tool(value)
        elif value["id"] not in seen_tools:
            seen_tools.add(value["id"])
            if on_tool:
                on_tool(value)

    for file in files:
        try:
            readers[agent](file, step, tool)
        except (OSError, ValueError, TypeError, AttributeError) as error:
            warnings.append("%s: %s" % (file, error))
    return {"files": len(files), "steps": len(seen), "warnings": warnings}


def price_table(config):
    prices = config.get("prices") or []
    if isinstance(prices, dict):
        prices = [("." if key == "default" else key, value) for key, value in prices.items() if key != "cacheReadPrice"]
    return [(re.compile(pattern, re.I), values) for pattern, values in prices]


def usd_of(usage, model, config):
    price = next((values for pattern, values in price_table(config) if pattern.search(model)), None)
    cached_price = config.get("cacheReadPrice")
    if cached_price is None and isinstance(config.get("prices"), dict):
        cached_price = config["prices"].get("cacheReadPrice")
    if price is None or (usage["cacheRead"] and cached_price is None):
        return None
    return (usage["freshPlain"] * price[0] + usage["cacheW5"] * price[0] * 1.25 + usage["cacheW1h"] * price[0] * 2
            + usage["cacheRead"] * (cached_price or 0) + usage["output"] * price[1]) / 1000000
