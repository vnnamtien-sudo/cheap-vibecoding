#!/usr/bin/env python3
"""Compare configured stages using read-only local session evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.lib.gate_config import load_config
from tools.lib.sessions import AGENTS, session_roots, timestamp, usd_of, walk

TEST = re.compile(r"\b(?:pytest|unittest|vitest|jest|ctest)\b|\b(?:node\s+--test|npm\s+(?:run\s+)?test|go\s+test|cargo\s+test)\b", re.I)


def blank():
    return {"cost": 0, "subCost": 0, "fresh": 0, "steps": 0, "replies": 0, "ctxSum": 0,
            "readLim": 0, "readAll": 0, "tests": 0, "testLong": 0, "code": 0, "ctx": {}, "runs": {},
            "first": None, "last": None, "deliveries": 0, "hours": {}, "unpricedReplies": 0}


def ratio(number, denominator, digits=1):
    return round(number / denominator, digits) if number is not None and denominator not in (None, 0) else None


def iso(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def periods_of(config, now):
    periods, groups = [], {}
    for item in config.get("stages", []):
        start, end = timestamp(item.get("from")), timestamp(item.get("to")) if item.get("to") else now
        key = item.get("key")
        if not key or key in groups or start is None or end is None or end <= start:
            raise ValueError("stage keys must be unique and each stage needs a valid from/to range")
        if any(start < other["end"] and end > other["start"] for other in periods):
            raise ValueError("stage time ranges must not overlap")
        periods.append({"key": key, "name": item.get("name", key), "start": start, "end": end})
        groups[key] = blank()

    return periods, groups


def callbacks(agent, periods, groups, config, now):
    def stage_of(value):
        return next((item for item in periods if item["start"] <= value < item["end"]), None)

    pending = {}

    def step(value):
        period = stage_of(value["t"])
        deepseek = "deepseek" in value["model"].lower()
        if not period or value["t"] > now or (agent == "deepseek" and not deepseek) or (agent == "claude" and deepseek):
            return
        group = groups[period["key"]]
        cost = usd_of(value["u"], value["model"], config)
        group["replies"] += 1
        group["fresh"] += value["u"]["fresh"]
        group["ctxSum"] += value["u"]["ctx"]
        group["first"] = min(group["first"], value["t"]) if group["first"] is not None else value["t"]
        group["last"] = max(group["last"], value["t"]) if group["last"] is not None else value["t"]
        run = group["runs"].setdefault(value["runId"], {"sub": value["sub"], "cost": 0})
        if cost is None:
            group["cost"] = run["cost"] = None
            group["unpricedReplies"] += 1
            if value["sub"]:
                group["subCost"] = None
        else:
            if group["cost"] is not None:
                group["cost"] += cost
            if run["cost"] is not None:
                run["cost"] += cost
            if value["sub"] and group["subCost"] is not None:
                group["subCost"] += cost
            hour = int(value["t"] // 3600000)
            group["hours"][hour] = group["hours"].get(hour, 0) + cost
        if not value["sub"]:
            group["ctx"][value["sid"]] = max(group["ctx"].get(value["sid"], 0), value["u"]["ctx"])

    def tool(value):
        if value.get("done") is not None:
            started = pending.pop(value["id"], None)
            if started:
                group = groups[started[0]]
                group["tests"] += 1
                group["testLong"] += int(value["done"] - started[1] > 600000)
            return
        period = stage_of(value["t"])
        if not period or value["t"] > now:
            return
        group = groups[period["key"]]
        group["steps"] += 1
        group["readLim"] += int(value.get("read") == "part")
        group["readAll"] += int(value.get("read") == "all")
        group["code"] += value.get("codeChars", 0)
        if value.get("shell") and TEST.search(value["shell"]) and not value.get("bg"):
            pending[value["id"]] = (period["key"], value["t"])

    return step, tool


def count_deliveries(periods, groups, deliveries):
    def stage_of(value):
        return next((item for item in periods if item["start"] <= value < item["end"]), None)

    if deliveries:
        for file in sorted(Path(deliveries).iterdir()):
            match = re.match(r"^(\d{4}-\d{2}-\d{2})", file.name)
            if not match or not file.is_file():
                continue
            at = timestamp(match.group(1) + "T12:00:00Z")
            stat = file.stat()
            created = getattr(stat, "st_birthtime", stat.st_mtime) * 1000
            if iso(created)[:10] == match.group(1):
                at = created
            period = stage_of(at) if at is not None else None
            if period:
                groups[period["key"]]["deliveries"] += 1


def stage_rows(periods, groups, config, now, deliveries):
    result = {}
    for period in periods:
        group = groups[period["key"]]
        if not group["steps"] and not group["replies"] and not group["deliveries"]:
            continue
        cost, contexts = group["cost"], list(group["ctx"].values())
        runs = list(group["runs"].values())
        active = None if group["unpricedReplies"] else sum(value >= config.get("activeHourMinUSD", 1) for value in group["hours"].values())

        def average(sub):
            selected = [run["cost"] for run in runs if run["sub"] == sub]
            return ratio(sum(selected), len(selected), 6) if selected and all(value is not None for value in selected) else None

        start = max(period["start"], group["first"]) if group["first"] is not None else period["start"]
        end = min(period["end"], now)
        row = {"name": period["name"], "from": iso(start), "to": iso(end), "days": round((end - start) / 86400000, 1),
               "costUSD": round(cost, 6) if cost is not None else None, "unpricedReplies": group["unpricedReplies"],
               "steps": group["steps"], "replies": group["replies"], "centPerStep": ratio(None if cost is None else cost * 100, group["steps"]),
               "freshInKPerStep": ratio(group["fresh"], group["steps"] * 1000, 2), "ctxKPerReply": ratio(group["ctxSum"], group["replies"] * 1000, 2),
               "wholeFileReadPct": ratio(group["readAll"] * 100, max(1, group["readAll"] + group["readLim"])),
               "subagentCostPct": ratio(None if group["subCost"] is None else group["subCost"] * 100, cost),
               "sessions": len(contexts), "bigContextPct": ratio(sum(value > config.get("bigContextTokens", 250000) for value in contexts) * 100, max(1, len(contexts))),
               "foregroundTests": group["tests"], "testsOver10minPct": ratio(group["testLong"] * 100, max(1, group["tests"])),
               "codeChars": group["code"], "codeCharsPerUSD": ratio(group["code"], cost), "usdPerSubagentRun": average(True),
               "usdPerSession": average(False), "activeHours": active, "usdPerActiveHour": ratio(cost, max(1, active) if active is not None else None, 6)}
        if deliveries:
            row.update(deliveries=group["deliveries"], usdPerDelivery=ratio(cost, max(1, group["deliveries"]), 6),
                       deliveriesPerActiveHour=ratio(group["deliveries"], max(1, active) if active is not None else None, 2))
        result[period["key"]] = row
    return result


def summarize(agent, roots, config, now=None, deliveries=None):
    now = time.time() * 1000 if now is None else now
    periods, groups = periods_of(config, now)
    step, tool = callbacks(agent, periods, groups, config, now)
    readback = walk(agent, roots=roots, on_step=step, on_tool=tool)
    count_deliveries(periods, groups, deliveries)
    result = stage_rows(periods, groups, config, now, deliveries)
    return {"agent": agent, "files": readback["files"], "uniqueReplies": readback["steps"], "sourceRoots": roots,
            "estimatedCost": True, "stages": result, "warnings": readback["warnings"] + ([] if roots else ["No session roots configured; set stages.sessionRoots or --root."])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--agent", choices=AGENTS)
    parser.add_argument("--root", "--projects", action="append")
    parser.add_argument("--deliveries")
    parser.add_argument("--out")
    parser.add_argument("--now")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path.cwd()
    config = load_config(root, config_path=args.config).get("stages", {})
    agent = args.agent or config.get("agent", "claude")
    now = timestamp(args.now) if args.now else time.time() * 1000
    if now is None:
        raise ValueError("invalid --now timestamp")
    deliveries = args.deliveries or config.get("deliveriesRoot")
    if deliveries:
        deliveries = Path(deliveries).expanduser()
        deliveries = deliveries if deliveries.is_absolute() else root / deliveries
    report = summarize(agent, session_roots(config, agent, root, args.root), config, now, deliveries)
    text = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if args.json:
        print(text)
    else:
        for key, row in report["stages"].items():
            cost = "unknown" if row["costUSD"] is None else "$%.6f estimate" % row["costUSD"]
            print("%s %s: USD=%s steps=%s replies=%s full-file=%s%% tests=%s" %
                  (key, row["name"], cost, row["steps"], row["replies"], row["wholeFileReadPct"], row["foregroundTests"]))
        for warning in report["warnings"]:
            print("warning: " + warning, file=sys.stderr)
        if args.out:
            print("Report: " + args.out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError) as error:
        print("stages: " + str(error), file=sys.stderr)
        sys.exit(2)
