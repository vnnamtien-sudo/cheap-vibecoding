#!/usr/bin/env python3
"""Check changed code, then run configured argv commands, writing a JSON receipt."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from lib.gate_config import config_location, load_config
from lib.gate_git import CODE_EXTENSIONS, changed_names, create_index_snapshot, project_root, read_changed
from lib.gate_structure import check_structure
from lib.process_runner import run_command as run_process


class GateParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def arguments():
    parser = GateParser(description=__doc__)
    parser.add_argument("--root", help="Project checkout root; defaults to Git root or cwd")
    parser.add_argument("--config", help="JSON config path, relative to --root unless absolute")
    parser.add_argument("--staged", action="store_true", help="Check and execute the staged index snapshot")
    parser.add_argument("--receipt", default=".gate/self-check.json", help="JSON output path relative to root")
    return parser.parse_args()


def run_command(name, command, root, files, timeout, config_path):
    argv = []
    for item in command:
        argv.extend(files if item == "{files}" else [sys.executable if item == "{python}" else item])
    check = {"name": name, "status": "failed", "argv": argv}
    try:
        result = run_process(argv, cwd=str(root), capture_output=True, text=False, timeout=timeout,
                             env=dict(os.environ, GATE_CONFIG_PATH=str(config_path),
                                      GATE_CONFIG_ROOT=str(Path(root).resolve())))
        check.update(exitCode=result.returncode, status="passed" if result.returncode == 0 else "failed",
                     stdout=result.stdout.decode("utf-8", "replace")[-16000:],
                     stderr=result.stderr.decode("utf-8", "replace")[-16000:])
        try:
            mapping = json.loads(check["stdout"].splitlines()[0]) if check["stdout"] else {}
        except ValueError:
            mapping = {}
        if isinstance(mapping, dict) and mapping.get("status") == "noMapping":
            check["noMapping"] = True
            check["status"] = "failed"
            check["reason"] = "noMapping: changed code lacks supported targeted tests"
    except subprocess.TimeoutExpired as error:
        check.update(reason="Command timed out after {} seconds".format(timeout), exitCode=None,
                     stdout=(error.stdout or b"").decode("utf-8", "replace")[-16000:],
                     stderr=(error.stderr or b"").decode("utf-8", "replace")[-16000:])
    except (OSError, ValueError) as error:
        check.update(reason=str(error), exitCode=None)
    return check


def command_checks(receipt, config, root, config_path):
    blocked = not all(check["status"] != "failed" for check in receipt["checks"])
    for name, key in (("type-check", "typeCheckCommand"), ("tests", "testCommand"), ("data-check", "dataCheckCommand")):
        files = receipt["changedFiles"] if name == "data-check" else receipt["codeFiles"]
        if blocked:
            check = {"name": name, "status": "skipped", "reason": "An earlier check failed"}
        elif not files:
            check = {"name": name, "status": "skipped", "reason": "No changed files" if name == "data-check" else "No changed code files"}
        elif not config[key]:
            check = {"name": name, "status": "failed" if name == "tests" else "skipped",
                     "reason": "No targeted test command configured" if name == "tests" else "Command is not configured"}
        else:
            check = run_command(name, config[key], root, files,
                                config["testQueue"].get("timeoutSeconds", 900), config_path)
        receipt["checks"].append(check)
        blocked = blocked or check["status"] == "failed"


def inspect_project(receipt, root, source, staged, config_arg):
    location = config_location(root, config_arg).resolve()
    if staged and location.is_relative_to(root):
        config_path = source / location.relative_to(root)
        config = load_config(source, location.relative_to(root) if config_arg is not None else None)
        receipt["configSource"] = "index-snapshot"
    else:
        config_path = location
        config = load_config(root, config_arg)
        receipt["configSource"] = "working-tree" if not staged else "external-config"
    receipt["config"] = str(location)
    names = changed_names(root, staged)
    files, ignored = read_changed(root, names, staged)
    receipt["changedFiles"] = sorted(files)
    receipt["ignoredFiles"] = ignored
    code = {name: text for name, text in files.items() if Path(name).suffix.lower() in CODE_EXTENSIONS}
    receipt["codeFiles"] = sorted(code)
    violations, limitations = check_structure(source, files, config)
    receipt["limitations"] = limitations
    receipt["checks"].append({"name": "structure", "status": "failed" if violations else "passed",
                              "violations": violations})
    command_checks(receipt, config, source, config_path)


def prepare_metadata(root):
    scratch = root / ".gate"
    if scratch.exists() and (scratch.is_symlink() or bool(getattr(scratch.lstat(), "st_file_attributes", 0) & 0x400)):
        raise ValueError("Gate metadata directory must not be a symbolic link")
    scratch.mkdir(exist_ok=True)
    ignored = scratch / ".gitignore"
    if ignored.is_symlink():
        raise ValueError("Gate metadata ignore file must not be a symbolic link")
    if not ignored.exists():
        ignored.write_text("*\n", encoding="utf-8")
    return scratch


def write_receipt(path, receipt):
    probe = path
    while probe != probe.parent:
        if probe.is_symlink() or (probe.exists() and bool(getattr(probe.lstat(), "st_file_attributes", 0) & 0x400)):
            raise OSError("Receipt path must not traverse symbolic links")
        probe = probe.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    root = Path.cwd().resolve()
    receipt_path = root / ".gate/self-check.json"
    receipt = {"schema": "gate-self-check/v1", "createdAt": datetime.now(timezone.utc).isoformat(),
               "ok": False, "mode": "working", "root": str(root), "checks": [],
               "changedFiles": [], "codeFiles": [], "ignoredFiles": [], "limitations": []}
    try:
        args = arguments()
        root = project_root(args.root)
        output = Path(args.receipt)
        selected = output if output.is_absolute() else root / output
        if not selected.resolve().is_relative_to(root):
            raise ValueError("Receipt path must stay inside the selected project")
        receipt_path = selected
        receipt.update(root=str(root), mode="staged" if args.staged else "working",
                       commandSource="index-snapshot" if args.staged else "working-tree")
        scratch = prepare_metadata(root)
        if args.staged:
            with tempfile.TemporaryDirectory(prefix="index-", dir=str(scratch)) as directory:
                snapshot = create_index_snapshot(root, Path(directory))
                inspect_project(receipt, root, snapshot, True, args.config)
        else:
            inspect_project(receipt, root, root, False, args.config)
        receipt["ok"] = not any(check["status"] == "failed" for check in receipt["checks"])
    except (OSError, ValueError, UnicodeError) as error:
        receipt["checks"].append({"name": "configuration" if not receipt["checks"] else "gate",
                                  "status": "failed", "reason": str(error)})
    try:
        write_receipt(receipt_path, receipt)
    except OSError as error:
        print("Cannot write gate receipt: {}".format(error), file=sys.stderr)
        return 1
    print("{}: {}".format("PASS" if receipt["ok"] else "FAIL", receipt_path))
    for check in receipt["checks"]:
        if check["status"] == "failed":
            print("{}: {}".format(check["name"], check.get("reason", check.get("violations", []))), file=sys.stderr)
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
