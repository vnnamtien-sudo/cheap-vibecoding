"""Shared JSON configuration; no shell strings or project code evaluation."""
import copy
import json
from pathlib import Path, PurePosixPath
import re

from .gate_extensions import validate_extensions


class ConfigError(ValueError):
    """The project gate configuration cannot safely be used."""


DEFAULT_CONFIG = {
    "maxFileLines": 400,
    "maxFunctionLines": 80,
    "bannedPatterns": [],
    "layers": [],
    "testCommand": [],
    "typeCheckCommand": [],
    "dataCheckCommand": [],
    "readLimitLines": 60,
    "accountMode": "single",
    "roles": {},
    "testQueue": {"mode": "targeted", "timeoutSeconds": 900, "hookEnabled": False},
    "testMappings": {},
}


def defaults():
    return copy.deepcopy(DEFAULT_CONFIG)


def config_location(root, config_path=None):
    path = Path(config_path) if config_path is not None else Path("gate.config.json")
    return path if path.is_absolute() else Path(root) / path


def _positive_integer(value, key):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError("{} must be a positive integer".format(key))


def _relative_path(value, key):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ConfigError("{} must be a relative path using '/'".format(key))
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or ":" in value or value.startswith("-"):
        raise ConfigError("{} must stay inside the project".format(key))
    return path.as_posix().rstrip("/")


def compile_pattern(item):
    if not isinstance(item, dict) or not isinstance(item.get("pattern"), str):
        raise ConfigError("bannedPatterns entries require a string pattern")
    if not isinstance(item.get("description"), str) or not item["description"]:
        raise ConfigError("bannedPatterns entries require a description")
    flags = item.get("flags", "")
    if not isinstance(flags, str) or any(flag not in "ims" for flag in flags):
        raise ConfigError("bannedPatterns flags support only i, m, s")
    bits = sum(value for key, value in (("i", re.I), ("m", re.M), ("s", re.S)) if key in flags)
    try:
        return re.compile(item["pattern"], bits)
    except re.error as error:
        raise ConfigError("Invalid bannedPatterns regex: {}".format(error)) from error


def _validate_command(config, key):
    command = config[key]
    if not isinstance(command, list) or any(not isinstance(arg, str) or "\x00" in arg for arg in command):
        raise ConfigError("{} must be an argv array of strings; shell commands are unsupported".format(key))
    if command and not command[0]:
        raise ConfigError("{} requires a nonempty executable".format(key))
    if any("{files}" in arg and arg != "{files}" for arg in command):
        raise ConfigError("{} must use {{files}} as an entire argv item".format(key))
    if any("{python}" in arg and arg != "{python}" for arg in command):
        raise ConfigError("{} must use {{python}} as an entire argv item".format(key))
    if key == "testCommand" and command and "{files}" not in command:
        raise ConfigError("testCommand must include a separate {files} argument for targeted tests")


def _validate_layers(config):
    layers = config["layers"]
    if not isinstance(layers, list):
        raise ConfigError("layers must be an array")
    identities = set()
    paths = set()
    for layer in layers:
        if not isinstance(layer, dict):
            raise ConfigError("layers entries must be objects")
        path = _relative_path(layer.get("path"), "layers.path")
        name = layer.get("name", path)
        if not isinstance(name, str) or not name or name in identities or path in paths:
            raise ConfigError("layers require unique, nonempty paths and names")
        identities.add(name)
        paths.add(path)
        allowed = layer.get("allow")
        if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
            raise ConfigError("layers.allow must be an array of layer names or paths")
    valid = identities | paths
    for layer in layers:
        for item in layer["allow"]:
            if item not in valid:
                _relative_path(item, "layers.allow")


def validate_config(value):
    if not isinstance(value, dict):
        raise ConfigError("gate.config.json must contain a JSON object")
    config = defaults()
    config.update(copy.deepcopy(value))
    for key in ("maxFileLines", "maxFunctionLines", "readLimitLines"):
        _positive_integer(config[key], key)
    if not isinstance(config["bannedPatterns"], list):
        raise ConfigError("bannedPatterns must be an array")
    for item in config["bannedPatterns"]:
        compile_pattern(item)
    _validate_layers(config)
    for key in ("testCommand", "typeCheckCommand", "dataCheckCommand"):
        _validate_command(config, key)
    mappings = config["testMappings"]
    if not isinstance(mappings, dict):
        raise ConfigError("testMappings must be an object of path to test-path arrays")
    for source, targets in mappings.items():
        if not isinstance(source, str):
            raise ConfigError("testMappings sources must be relative path strings")
        _relative_path(source.rstrip("/"), "testMappings source")
        if not isinstance(targets, list) or not targets or any(not isinstance(target, str) for target in targets):
            raise ConfigError("testMappings values must be test-path arrays")
        for target in targets:
            _relative_path(target, "testMappings target")
    if not isinstance(config["roles"], (dict, list)):
        raise ConfigError("roles must be an object or array")
    for key in ("testQueue", "stages", "tokenUsage", "privacy"):
        if key in config and not isinstance(config[key], dict):
            raise ConfigError("{} must be an object".format(key))
    if "privacy" in config:
        patterns = config["privacy"].get("patterns", [])
        if not isinstance(patterns, list):
            raise ConfigError("privacy.patterns must be an array")
        for pattern in patterns:
            compile_pattern(pattern)
    queue = config["testQueue"]
    if "timeoutSeconds" in queue:
        _positive_integer(queue["timeoutSeconds"], "testQueue.timeoutSeconds")
    if "hookEnabled" in queue and not isinstance(queue["hookEnabled"], bool):
        raise ConfigError("testQueue.hookEnabled must be a boolean")
    try:
        validate_extensions(config)
    except ValueError as error:
        raise ConfigError(str(error)) from error
    return config


def load_config(root, config_path=None):
    path = config_location(root, config_path)
    if not path.exists():
        if config_path is not None:
            raise ConfigError("Configuration does not exist: {}".format(path))
        return defaults()
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ConfigError("Cannot read configuration {}: {}".format(path, error)) from error
    return validate_config(value)
