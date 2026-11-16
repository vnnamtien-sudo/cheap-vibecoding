#!/usr/bin/env python3
"""Map changed files to concrete unittest/Node tests without evaluating source."""
import argparse
import ast
from collections import defaultdict, deque
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


IGNORED = {".git", ".gate", ".work", "node_modules", "vendor", ".venv", "venv", "env",
           "__pycache__", "dist", "build", "coverage", "target", ".next", ".cache"}
JS = {".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx"}
CODE = JS | {".py", ".pyi", ".java", ".kt", ".go", ".rs", ".rb", ".php", ".cs",
             ".c", ".h", ".cpp", ".hpp", ".swift", ".ps1", ".cmd", ".bat", ".sh",
             ".sql", ".css", ".scss", ".vue", ".svelte"}
JS_IMPORT = re.compile(r"(?:\b(?:require|import)\s*\(\s*|\bfrom\s+|\bimport\s*)['\"]([^'\"]+)['\"]")


def linked(path):
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def project_files(root):
    found = []
    for directory, children, names in os.walk(str(root), followlinks=False):
        parent = Path(directory)
        children[:] = sorted(name for name in children if name not in IGNORED and not linked(parent / name))
        for name in sorted(names):
            file = parent / name
            if not linked(file):
                found.append(file.relative_to(root).as_posix())
    return sorted(found)


def read_source(root, name):
    try:
        return (root / name).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return ""


def test_file(name):
    path = PurePosixPath(name)
    return (path.suffix == ".py" and path.name.startswith("test_")) or bool(
        re.search(r"\.(?:test|spec)\.(?:cjs|mjs|js)$", name))


def _test_key(name):
    path = PurePosixPath(name)
    stem = path.stem.removeprefix("test_")
    stem = re.sub(r"\.(?:test|spec)$", "", stem).replace("-", "_")
    parts = list(path.parent.parts)
    while parts and parts[0] in ("tests", "test", "src", "tools"):
        parts.pop(0)
    return "/".join(parts + [stem])


def _frameworks(root, files, sources):
    result = set()
    if any("unittest" in sources[name] for name in files if name.endswith(".py") and test_file(name)):
        result.add("unittest")
    try:
        package = json.loads(read_source(root, "package.json") or "{}")
        scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
        if isinstance(scripts, dict) and any(re.search(r"\bnode\s+--test\b", str(value)) for value in scripts.values()):
            result.add("node")
    except (ValueError, TypeError):
        pass
    if any("node:test" in sources[name] for name in sources if test_file(name) and Path(name).suffix in JS):
        result.add("node")
    return result


def _python_dependencies(name, text, python_files):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set()
    found = set()
    dotted = {file: file[:-3].replace("/", ".") for file in python_files}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [".".join(filter(None, (node.module, alias.name))) for alias in node.names]
            if node.module:
                modules.append(node.module)
            if node.level:
                parts = list(PurePosixPath(name).parent.parts)
                parts = parts[:len(parts) - node.level + 1]
                modules = [".".join(parts + [module]) for module in modules]
        else:
            continue
        for module in modules:
            matches = [file for file, value in dotted.items() if value == module or value.endswith("." + module)]
            if len(matches) == 1:
                found.add(matches[0])
    return found


def _js_dependencies(root, name, text, sources):
    found = set()
    for specifier in JS_IMPORT.findall(text):
        if not specifier.startswith("."):
            continue
        target = (root / PurePosixPath(name).parent / specifier).resolve()
        if not target.is_relative_to(root):
            continue
        relative = target.relative_to(root).as_posix()
        candidates = [relative] + [relative + suffix for suffix in JS]
        candidates += [relative + "/index" + suffix for suffix in JS]
        found.update(candidate for candidate in candidates if candidate in sources)
    return found


def _reverse_dependencies(root, sources):
    reverse = defaultdict(set)
    python_files = [name for name in sources if name.endswith(".py")]
    for name, text in sources.items():
        dependencies = (_python_dependencies(name, text, python_files) if name.endswith(".py")
                        else _js_dependencies(root, name, text, sources))
        for dependency in dependencies:
            reverse[dependency].add(name)
    return reverse


def _related_tests(changed, sources, tests, reverse):
    selected = set()
    pending = deque([changed])
    seen = set()
    while pending:
        name = pending.popleft()
        if name in seen:
            continue
        seen.add(name)
        if name in tests:
            selected.add(name)
        key = _test_key(name)
        exact = [test for test in tests if _test_key(test) == key]
        if not exact:
            same_stem = [file for file in sources if not test_file(file)
                         and _test_key(file).split("/")[-1] == key.split("/")[-1]]
            if len(same_stem) == 1:
                exact = [test for test in tests if _test_key(test).split("/")[-1] == key.split("/")[-1]]
        selected.update(exact)
        pending.extend(sorted(reverse.get(name, ())))
    return sorted(selected)


def _safe_changed(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or ":" in name
            or "\\" in name or name.startswith("-") or "\x00" in name):
        raise ValueError("Changed paths must be relative paths inside the project")
    return path.as_posix()


def _explicit_mappings(root):
    selected = root / "gate.config.json"
    config_root = os.environ.get("GATE_CONFIG_ROOT")
    if config_root and Path(config_root).resolve() == root.resolve():
        selected = Path(os.environ.get("GATE_CONFIG_PATH", str(selected)))
    if not selected.is_file():
        return {}
    value = json.loads(selected.read_text(encoding="utf-8-sig"))
    mappings = value.get("testMappings", {}) if isinstance(value, dict) else None
    if not isinstance(mappings, dict):
        raise ValueError("testMappings must be an object")
    for name, tests in mappings.items():
        _safe_changed(name.rstrip("/"))
        if not isinstance(tests, list) or not tests or any(not isinstance(test, str) for test in tests):
            raise ValueError("testMappings entries require nonempty test path arrays")
        for test in tests:
            _safe_changed(test)
    return mappings


def _mapped_tests(name, mappings, tests):
    selected = set()
    for key in sorted(mappings, key=len, reverse=True):
        if name != key and not (key.endswith("/") and name.startswith(key)):
            continue
        invalid = set(mappings[key]) - tests
        if invalid:
            raise ValueError("testMappings target is missing or unsupported: {}".format(sorted(invalid)))
        selected.update(mappings[key])
    return selected


def plan_tests(root, changed):
    names = sorted({_safe_changed(name) for name in changed})
    files = project_files(root)
    sources = {name: read_source(root, name) for name in files if Path(name).suffix in JS | {".py"}}
    frameworks = _frameworks(root, files, sources)
    tests = {name for name in sources if test_file(name) and (
        (name.endswith(".py") and "unittest" in frameworks) or (Path(name).suffix in JS and "node" in frameworks))}
    reverse = _reverse_dependencies(root, sources)
    explicit = _explicit_mappings(root)
    mappings = {}
    missing = []
    for name in names:
        if Path(name).suffix not in CODE:
            continue
        related = set(_related_tests(name, sources, tests, reverse)) if name in sources else set()
        related.update(_mapped_tests(name, explicit, tests))
        if related:
            mappings[name] = sorted(related)
        else:
            missing.append(name)
    selected = sorted({test for matches in mappings.values() for test in matches})
    python = [name[:-3].replace("/", ".") for name in selected if name.endswith(".py")]
    invalid = [name for name in python if not all(part.isidentifier() for part in name.split("."))]
    if invalid:
        missing.extend(invalid)
    commands = []
    if python and not invalid:
        commands.append([sys.executable, "-m", "unittest", *python])
    node = [name for name in selected if not name.endswith(".py")]
    if node:
        commands.append(["node", "--test", *node])
    return {"status": "noMapping" if missing else "planned" if commands else "skipped",
            "reason": "No changed code requiring tests" if not commands and not missing else "",
            "mappings": mappings, "tests": selected, "noMapping": sorted(missing), "commands": commands}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Print the mapping without running tests")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    try:
        plan = plan_tests(Path.cwd().resolve(), args.files)
    except (OSError, ValueError, UnicodeError) as error:
        print(json.dumps({"status": "noMapping", "reason": str(error)}))
        return 1
    print(json.dumps(plan, ensure_ascii=False), flush=True)
    if plan["status"] == "noMapping":
        return 1
    if args.plan or not plan["commands"]:
        return 0
    for command in plan["commands"]:
        try:
            result = subprocess.run(command, cwd=str(Path.cwd()), shell=False, capture_output=True)
        except OSError as error:
            print(str(error), file=sys.stderr)
            return 1
        output = (result.stdout or b"").decode("utf-8", "replace")
        errors = (result.stderr or b"").decode("utf-8", "replace")
        sys.stdout.write(output)
        sys.stderr.write(errors)
        if "unittest" in command and re.search(r"\bRan\s+0\s+tests\b", output + errors):
            print("no tests ran for the mapped unittest modules", file=sys.stderr)
            return 1
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
