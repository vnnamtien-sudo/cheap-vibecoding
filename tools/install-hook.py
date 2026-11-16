#!/usr/bin/env python3
"""Install an optional Git pre-commit gate without overwriting another hook."""
import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path


def install(root, python_command):
    root = Path(root).resolve()
    if python_command not in ("python3", "python", "py"):
        raise ValueError("Use python3, python or py as the interpreter command")
    if not (root / "gate.config.json").is_file():
        raise ValueError("Run tools/init.py for the target project first")
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
                            check=True, capture_output=True, text=True)
    directory = Path(result.stdout.strip())
    if not directory.is_absolute():
        directory = root / directory
    directory.mkdir(parents=True, exist_ok=True)
    hook = directory / "pre-commit"
    command = [sys.executable, str(Path(__file__).with_name("self-check.py").resolve()),
               "--root", str(root), "--staged"]
    body = (f"#!/usr/bin/env {python_command}\n"
            '"""Locally generated gate; reinstall if the tool checkout moves."""\n'
            "import subprocess\nimport sys\n"
            f"sys.exit(subprocess.call({command!r}))\n")
    with hook.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--python-command", default="python" if os.name == "nt" else "python3")
    args = parser.parse_args()
    try:
        print("Installed optional hook:", install(args.root, args.python_command))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("Hook not installed:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
