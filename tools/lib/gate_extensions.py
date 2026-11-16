"""Validation for optional runtime tool extensions to the shared configuration."""
from datetime import datetime, timezone
import math
import re


def _number(value, key, minimum=0, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or value < minimum or (integer and not isinstance(value, int))):
        raise ValueError("{} must be a finite {} >= {}".format(key, "integer" if integer else "number", minimum))


def _string(value, key):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("{} must be a nonempty string".format(key))


def _regex(value, key, capture=False):
    _string(value, key)
    try:
        compiled = re.compile(value)
    except re.error as error:
        raise ValueError("Invalid {} regex: {}".format(key, error)) from error
    if capture and not compiled.groups:
        raise ValueError("{} must capture its worker count".format(key))


def _roots(value, key):
    agents = {"claude", "codex", "gemini", "deepseek"}
    if not isinstance(value, dict) or any(agent not in agents for agent in value):
        raise ValueError("{} must map supported agent names to path arrays".format(key))
    for agent, paths in value.items():
        if not isinstance(paths, list):
            raise ValueError("{}.{} must be a path array".format(key, agent))
        for path in paths:
            _string(path, key + "." + agent)


def _prices(config, key):
    prices = config.get("prices", [])
    cached = config.get("cacheReadPrice")
    if cached is not None:
        _number(cached, key + ".cacheReadPrice")
    if isinstance(prices, dict):
        if prices.get("cacheReadPrice") is not None:
            _number(prices["cacheReadPrice"], key + ".prices.cacheReadPrice")
        prices = [("." if pattern == "default" else pattern, rates)
                  for pattern, rates in prices.items() if pattern != "cacheReadPrice"]
    if not isinstance(prices, list):
        raise ValueError(key + ".prices must be an array or a legacy price object")
    for item in prices:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(key + ".prices entries must be [modelRegex, [inputRate, outputRate]]")
        _regex(item[0], key + ".prices model")
        rates = item[1]
        if not isinstance(rates, list) or len(rates) != 2:
            raise ValueError(key + ".prices needs exactly two rates")
        for rate in rates:
            _number(rate, key + ".prices rate")


def _iso(value, key):
    _string(value, key)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(key + " must be an ISO date/time") from error
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _stage_windows(value):
    if not isinstance(value, list):
        raise ValueError("stages.stages must be an array")
    seen = set()
    windows = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("stages.stages entries must be objects")
        _string(item.get("key"), "stage.key")
        if item["key"] in seen:
            raise ValueError("stage keys must be unique")
        seen.add(item["key"])
        if "name" in item:
            _string(item["name"], "stage.name")
        start = _iso(item.get("from"), "stage.from")
        end = _iso(item["to"], "stage.to") if item.get("to") else datetime.max.replace(tzinfo=timezone.utc)
        if end <= start or any(start < other_end and end > other_start for other_start, other_end in windows):
            raise ValueError("stage ranges must be increasing and must not overlap")
        windows.append((start, end))


def _session_dirs(value):
    if not isinstance(value, list):
        raise ValueError("testQueue.sessionDirs must be an array")
    for descriptor in value:
        if not isinstance(descriptor, dict):
            raise ValueError("testQueue.sessionDirs entries must be objects")
        _string(descriptor.get("path"), "sessionDirs.path")
        for key in ("depth", "datedDays"):
            if key in descriptor:
                _number(descriptor[key], "sessionDirs." + key, 1, integer=True)
        if "ext" in descriptor:
            _string(descriptor["ext"], "sessionDirs.ext")


def _queue(config):
    if config.get("mode", "targeted") not in ("targeted", "advanced"):
        raise ValueError("testQueue.mode must be targeted or advanced")
    for key in ("slots", "minTestSlots", "autoWeight", "heavyMax", "pollMs"):
        if key in config:
            _number(config[key], "testQueue." + key, 1, integer=True)
    for key in ("staleMinutes", "activeSessionMinutes"):
        if key in config:
            _number(config[key], "testQueue." + key, 0.000001)
    for key in ("minFreeGB", "cooldownSeconds"):
        if key in config:
            _number(config[key], "testQueue." + key)
    for key in ("poolCountsSessions", "heavyOnlyLabels", "hookEnabled"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError("testQueue.{} must be a boolean".format(key))
    for key in ("dataDir", "transcriptsRoot"):
        if key in config:
            _string(config[key], "testQueue." + key)
    if "sessionRoots" in config:
        _roots(config["sessionRoots"], "testQueue.sessionRoots")
    if "sessionDirs" in config:
        _session_dirs(config["sessionDirs"])
    patterns = config.get("heavyPatterns", [])
    if not isinstance(patterns, list):
        raise ValueError("testQueue.heavyPatterns must be an array")
    for pattern in patterns:
        _regex(pattern, "testQueue.heavyPatterns")
    if config.get("workerPattern") is not None:
        _regex(config["workerPattern"], "testQueue.workerPattern", capture=True)
    if "heavyLabels" in config:
        _regex(config["heavyLabels"], "testQueue.heavyLabels")


def validate_extensions(config):
    _queue(config["testQueue"])
    for key in ("tokenUsage", "stages"):
        if key not in config:
            continue
        extension = config[key]
        agents = {"claude", "codex", "gemini", "deepseek"} | ({"all"} if key == "tokenUsage" else set())
        if "agent" in extension and (not isinstance(extension["agent"], str) or extension["agent"] not in agents):
            raise ValueError("{}.agent is unsupported".format(key))
        if "sessionRoots" in extension:
            _roots(extension["sessionRoots"], key + ".sessionRoots")
        _prices(extension, key)
        for field in ("days", "bigContextTokens"):
            if field in extension:
                _number(extension[field], key + "." + field, 1, integer=True)
        if "activeHourMinUSD" in extension:
            _number(extension["activeHourMinUSD"], key + ".activeHourMinUSD")
        if key == "stages" and "stages" in extension:
            _stage_windows(extension["stages"])
