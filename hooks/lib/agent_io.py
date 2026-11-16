"""Claude Code PreToolUse stdin/stdout adapter; no external runtime required."""
import argparse
import json
import sys


def normalize(value):
    if not isinstance(value, dict):
        raise ValueError("hook input must be a JSON object")
    if value.get("hook_event_name", "PreToolUse") != "PreToolUse":
        raise ValueError("only Claude PreToolUse events are supported")
    if not isinstance(value.get("tool_name"), str):
        raise ValueError("tool_name must be a string")
    if not isinstance(value.get("tool_input", {}), dict):
        raise ValueError("tool_input must be an object")
    if value.get("cwd") is not None and not isinstance(value["cwd"], str):
        raise ValueError("cwd must be a string")
    return value


def deny_output(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": str(reason)}}


def run_hook(decide, argv=None):
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--config")
        options, unknown = parser.parse_known_args(argv)
        if unknown:
            raise ValueError("unsupported hook arguments: " + " ".join(unknown))
        value = normalize(json.load(sys.stdin))
        reason = decide(value, config_path=options.config)
    except (Exception, SystemExit) as error:
        reason = "Hook input/configuration error: " + str(error)
    if reason:
        sys.stdout.write(json.dumps(deny_output(reason), ensure_ascii=True))
    return 0
