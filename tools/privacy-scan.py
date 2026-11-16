#!/usr/bin/env python3
"""Scan publishable Git files without printing sensitive matching values."""
import argparse
import json
import re
import subprocess
from pathlib import Path


def rules():
    return [
        ("absolute-drive-path", re.compile(r"(?i)\b[a-z]:[\\/]")),
        ("account-cycling", re.compile(r"(?i)multi[ -]?account|account\s+(?:rotation|cycling|swapping)|"
                                       r"rotat(?:e|ing)\s+accounts|(?:multiple|alternate)\s+accounts|switch(?:ing)?\s+accounts")),
        ("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
        ("credential", re.compile(r"\b(?:sk\x2d[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b")),
        ("long-hex", re.compile(r"(?i)\b[a-f0-9]{32,}\b")),
        ("fixed-framework", re.compile("(?i)\\b(?:" + "Djan" + "go|My" + "SQL)\\b")),
    ]


def candidates(root):
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True, check=True,
    )
    return sorted({name.decode("utf-8", "surrogateescape")
                   for name in result.stdout.split(b"\0") if name})


def scan(root, names, extra=()):
    findings = []
    patterns = rules() + [(item["description"], re.compile(item["pattern"])) for item in extra]
    for name in names:
        path = root / name
        if path.is_symlink():
            findings.append({"file": name, "line": 0, "rule": "symlink-review-required"})
            continue
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if b"\0" in raw:
            findings.append({"file": name, "line": 0, "rule": "binary-review-required"})
            continue
        try:
            lines = raw.decode("utf-8-sig").splitlines()
        except UnicodeDecodeError:
            findings.append({"file": name, "line": 0, "rule": "encoding-review-required"})
            continue
        for number, line in enumerate(lines, 1):
            for label, pattern in patterns:
                for match in pattern.finditer(line):
                    if label == "email":
                        local, domain = match.group().lower().split("@", 1)
                        if local == "noreply" or local.startswith("noreply+") or "noreply" in domain.split("."):
                            continue
                    if label == "fixed-framework" and (name.startswith("examples/") or name == "gate.config.example.json"):
                        continue
                    findings.append({"file": name, "line": number, "rule": label})
                    break
    return findings


def load_patterns(root, config):
    """Project terms: gate.config.json privacy.patterns plus .gate/private-patterns.json, which stays out of Git."""
    local = root / ".gate" / "private-patterns.json"
    extra = json.loads(local.read_text(encoding="utf-8-sig")) if local.exists() else []
    return list(config.get("privacy", {}).get("patterns", [])) + list(extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--receipt", default=".gate/privacy.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    receipt = {"passed": False, "files": 0, "findings": []}
    try:
        config_path = root / "gate.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {}
        names = candidates(root)
        names = [name for name in names if (root / name).exists() or (root / name).is_symlink()]
        receipt["files"] = len(names)
        receipt["findings"] = scan(root, names, load_patterns(root, config))
        receipt["passed"] = not receipt["findings"]
    except (OSError, ValueError, TypeError, KeyError, re.error, subprocess.CalledProcessError) as exc:
        receipt["error"] = type(exc).__name__ + ": scan could not finish"
    target = root / args.receipt
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": receipt["passed"], "files": receipt["files"],
                      "findings": len(receipt["findings"]), "receipt": args.receipt}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
