#!/usr/bin/env python3
"""Create a reviewable gate configuration by reading a project's files."""
import argparse
import copy
import json
from pathlib import Path
import sys

from lib.gate_config import config_location, defaults, load_config, validate_config
from lib.init_detect import scan_project


TOOL_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ".ai-gates/targeted-tests.py"


def generate_config(root):
    draft = defaults()
    template = TOOL_ROOT / "gate.config.example.json"
    if template.is_file():
        configured = load_config(TOOL_ROOT, template)
        for key in ("accountMode", "roles", "maxFileLines", "maxFunctionLines", "readLimitLines"):
            draft[key] = copy.deepcopy(configured[key])
    scan = scan_project(root)
    draft.update(detected=scan["detected"], layers=scan["layers"], review=scan["review"])
    if scan["detected"]["languages"]:
        draft["testCommand"] = ["{python}", HELPER_PATH, "{files}"]
    if scan["supportedTests"]:
        draft["testMappings"][HELPER_PATH] = scan["supportedTests"]
    return validate_config(draft)


def _inside_root(path, root):
    if not path.resolve().is_relative_to(root):
        raise ValueError("Generated paths must stay inside the selected project: {}".format(path))
    probe = path
    while probe != root and probe != probe.parent:
        if probe.exists() and (probe.is_symlink() or bool(getattr(probe.lstat(), "st_file_attributes", 0) & 0x400)):
            raise ValueError("Refusing to write through a linked path: {}".format(probe))
        probe = probe.parent


def initialize(root, config_path=None, force=False):
    target = config_location(root, config_path)
    _inside_root(target, root)
    if target.exists() and not force:
        return {"status": "preserved", "config": str(target), "reason": "Existing configuration was preserved"}
    draft = generate_config(root)
    helper = root / HELPER_PATH
    helper_source = TOOL_ROOT / "tools/targeted-tests.py"
    if draft["testCommand"]:
        _inside_root(helper, root)
        content = helper_source.read_bytes()
        if helper.exists() and helper.read_bytes() != content and not force:
            draft["testCommand"] = []
            draft["testMappings"] = {}
            draft["review"].append("testCommand remains empty: existing {} was preserved; inspect it or use --force.".format(HELPER_PATH))
        else:
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_bytes(content)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "generated", "config": str(target), "detected": draft["detected"], "review": draft["review"]}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Project directory (default: current directory)")
    parser.add_argument("--config", help="Configuration output path relative to the project")
    parser.add_argument("--force", action="store_true", help="Explicitly replace existing configuration/helper")
    args = parser.parse_args()
    try:
        root = Path(args.root or Path.cwd()).resolve()
        if not root.is_dir():
            raise ValueError("Project root is not a directory: {}".format(root))
        result = initialize(root, args.config, args.force)
    except (OSError, ValueError, UnicodeError) as error:
        print("Initialization failed: {}".format(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
