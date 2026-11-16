#!/usr/bin/env python3
"""Read local usage; USD estimates require explicit rates in gate.config.json."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.lib.gate_config import load_config
from tools.lib.sessions import AGENTS, session_roots, timestamp, usd_of, walk


def blank():
    return {"replies": 0, "fresh": 0, "cacheRead": 0, "output": 0, "usd": 0, "unpricedReplies": 0}


def add(group, usage, usd):
    group["replies"] += 1
    for field in ("fresh", "cacheRead", "output"):
        group[field] += usage[field]
    if usd is None:
        group["usd"] = None
        group["unpricedReplies"] += 1
    elif group["usd"] is not None:
        group["usd"] += usd


def summarize(agent, roots, config, days=7, windows=None, now=None):
    now = time.time() * 1000 if now is None else now
    windows = windows or []
    cutoff = now - days * 86400000
    since = min([cutoff] + [window[1] for window in windows])
    total, subs, by_day, by_model = blank(), blank(), {}, {}
    groups = [blank() for _ in windows]

    def step(value):
        if value["t"] < since or value["t"] > now:
            return
        deepseek = "deepseek" in value["model"].lower()
        if (agent == "deepseek" and not deepseek) or (agent == "claude" and deepseek):
            return
        usd = usd_of(value["u"], value["model"], config)
        for window, group in zip(windows, groups):
            if window[1] <= value["t"] < window[2]:
                add(group, value["u"], usd)
        if value["t"] < cutoff:
            return
        add(total, value["u"], usd)
        if value["sub"]:
            add(subs, value["u"], usd)
        day = datetime.fromtimestamp(value["t"] / 1000, timezone.utc).date().isoformat()
        add(by_day.setdefault(day, blank()), value["u"], usd)
        add(by_model.setdefault(value["model"], blank()), value["u"], usd)

    readback = walk(agent, roots=roots, since=since, on_step=step)
    return {"agent": agent, "files": readback["files"], "uniqueReplies": readback["steps"], "sourceRoots": roots,
            "estimatedCost": True, "total": total, "subagents": subs, "byDay": by_day, "byModel": by_model,
            "windows": {window[0]: group for window, group in zip(windows, groups)},
            "warnings": readback["warnings"] + ([] if roots else ["No session roots configured; set tokenUsage.sessionRoots or --root."])}


def line(name, group):
    total = group["fresh"] + group["cacheRead"] + group["output"]
    reread = 100 * group["cacheRead"] / total if total else 0
    cost = "unknown (configure prices)" if group["usd"] is None else "$%.6f (estimate)" % group["usd"]
    return "%s: replies=%s tokens=%s cached=%.1f%% output=%s USD=%s" % (name, group["replies"], total, reread, group["output"], cost)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--agent", choices=AGENTS + ("all",))
    parser.add_argument("--root", "--projects", action="append")
    parser.add_argument("--days", type=float)
    parser.add_argument("--week-reset")
    parser.add_argument("--five-hour-reset")
    parser.add_argument("--now", help="ISO timestamp for a reproducible report")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    config = load_config(root, config_path=args.config).get("tokenUsage", {})
    agent = args.agent or config.get("agent", "claude")
    days = args.days if args.days is not None else config.get("days", 7)
    if not isinstance(days, (int, float)) or isinstance(days, bool) or not math.isfinite(days) or days <= 0:
        raise ValueError("--days must be positive")
    now = timestamp(args.now) if args.now else time.time() * 1000
    if now is None:
        raise ValueError("invalid --now timestamp")
    windows = []
    for label, reset, length in (("week", args.week_reset, 7 * 86400000), ("fiveHours", args.five_hour_reset, 5 * 3600000)):
        if reset:
            end = timestamp(reset)
            if end is None:
                raise ValueError("invalid reset timestamp")
            windows.append((label, end - length, end))
    reports = {current: summarize(current, session_roots(config, current, root, args.root), config, days, windows, now)
               for current in AGENTS if agent in (current, "all")}
    if not reports:
        raise ValueError("unknown agent " + str(agent))
    if args.json:
        print(json.dumps(reports, ensure_ascii=True, indent=2, allow_nan=False))
    else:
        for current, report in reports.items():
            print(line(current, report["total"]))
            print(line("  subagents", report["subagents"]))
            for label, group in list(report["byModel"].items()) + list(report["byDay"].items()) + list(report["windows"].items()):
                print(line("  " + label, group))
            for warning in report["warnings"]:
                print("warning: " + warning, file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError) as error:
        print("token-usage: " + str(error), file=sys.stderr)
        sys.exit(2)
