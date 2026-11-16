"""Read-only language/framework inventory, using only Python's standard library."""
import json
import os
from pathlib import Path
import re


IGNORED = {".git", ".gate", ".work", ".ai-gates", "node_modules", "vendor", ".venv", "venv", "env",
           "__pycache__", "dist", "build", "coverage", "target", ".next", ".cache"}
LANGUAGES = {
    ".js": "JavaScript", ".cjs": "JavaScript", ".mjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".py": "Python", ".pyi": "Python",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby",
    ".php": "PHP", ".cs": "C#", ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++",
    ".swift": "Swift", ".ps1": "PowerShell", ".sh": "Shell", ".vue": "Vue", ".svelte": "Svelte",
}
LAYER_NAMES = {"api", "app", "application", "domain", "services", "service", "data", "models", "routes",
               "controllers", "infrastructure", "repositories", "components", "utils", "lib", "tests", "test",
               "tools", "hooks", "frontend", "backend", "client", "server"}


def _linked(path):
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def inventory(root):
    files = []
    directories = set()
    for directory, children, names in os.walk(str(root), followlinks=False):
        parent = Path(directory)
        children[:] = sorted(name for name in children if name not in IGNORED and not _linked(parent / name))
        for name in children:
            directories.add((parent / name).relative_to(root).as_posix())
        for name in sorted(names):
            path = parent / name
            if not _linked(path):
                files.append(path.relative_to(root).as_posix())
    return sorted(files), sorted(directories)


def read(root, name, review):
    try:
        return (root / name).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        review.append("Cannot inspect {}: {}".format(name, error))
        return ""


def package_json(root, files, review):
    if "package.json" not in files:
        return {}
    try:
        package = json.loads(read(root, "package.json", review))
        if not isinstance(package, dict):
            raise ValueError("manifest must contain an object")
        return package
    except (ValueError, TypeError) as error:
        review.append("Review malformed package.json: {}".format(error))
        return {}


def _package_managers(files, package):
    managers = set()
    locks = {"package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "pnpm-lock.yaml": "pnpm",
             "yarn.lock": "yarn", "bun.lock": "bun", "bun.lockb": "bun", "poetry.lock": "poetry",
             "Pipfile.lock": "pipenv", "uv.lock": "uv", "Cargo.lock": "cargo", "go.mod": "go"}
    for name in files:
        if Path(name).name in locks:
            managers.add(locks[Path(name).name])
    declared = package.get("packageManager", "")
    if isinstance(declared, str) and declared.split("@", 1)[0] in {"npm", "pnpm", "yarn", "bun"}:
        managers.add(declared.split("@", 1)[0])
    return sorted(managers)


def _javascript_frameworks(package):
    frameworks = set()
    tests = set()
    dependencies = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        values = package.get(key, {})
        if isinstance(values, dict):
            dependencies.update(values)
    for dependency, label in (("react", "React"), ("vue", "Vue"), ("next", "Next.js"),
                              ("nuxt", "Nuxt"), ("svelte", "Svelte"), ("express", "Express"),
                              ("@nestjs/core", "NestJS")):
        if dependency in dependencies:
            frameworks.add(label)
    scripts = package.get("scripts", {})
    command = " ".join(str(value) for value in scripts.values()) if isinstance(scripts, dict) else ""
    for dependency, label in (("vitest", "Vitest"), ("jest", "Jest"), ("mocha", "Mocha")):
        if dependency in dependencies or re.search(r"\b" + dependency + r"\b", command):
            tests.add(label)
    if re.search(r"\bnode\s+--test\b", command):
        tests.add("Node.js test runner")
    return frameworks, tests


def _python_frameworks(root, files, review):
    frameworks = set()
    tests = set()
    for name in files:
        if Path(name).name in ("pyproject.toml", "pytest.ini", "tox.ini", "requirements.txt", "setup.cfg"):
            text = read(root, name, review)
            if "pytest" in text or Path(name).name == "pytest.ini":
                tests.add("pytest")
            if Path(name).name == "requirements.txt":
                for dependency, label in (("fastapi", "FastAPI"), ("flask", "Flask")):
                    if re.search(r"(?im)^\s*" + dependency + r"(?:\s|[<>=~!\[]|$)", text):
                        frameworks.add(label)
        if name.endswith(".py") and Path(name).name.startswith("test_"):
            text = read(root, name, review)
            if re.search(r"(?m)^\s*(?:import\s+unittest\b|from\s+unittest\b)", text):
                tests.add("unittest")
            if re.search(r"(?m)^(?:\s*(?:import\s+pytest\b|from\s+pytest\b)|def\s+test_)", text):
                tests.add("pytest")
    return frameworks, tests


def scan_project(root):
    files, directories = inventory(root)
    review = []
    package = package_json(root, files, review)
    frameworks, tests = _javascript_frameworks(package)
    python_frameworks, python_tests = _python_frameworks(root, files, review)
    frameworks.update(python_frameworks)
    tests.update(python_tests)
    node_tests = []
    unit_tests = []
    for name in files:
        if re.search(r"\.(?:test|spec)\.(?:cjs|mjs|js)$", name):
            text = read(root, name, review)
            if "node:test" in text:
                tests.add("Node.js test runner")
            node_tests.append(name)
        elif name.endswith(".py") and Path(name).name.startswith("test_"):
            unit_tests.append(name)
    paths = [name for name in directories if Path(name).name in LAYER_NAMES and len(Path(name).parts) <= 3]
    layers = [{"path": name, "allow": list(paths)} for name in paths]
    languages = sorted({LANGUAGES[Path(name).suffix.lower()] for name in files
                        if Path(name).suffix.lower() in LANGUAGES})
    detected = {"languages": languages, "packageManagers": _package_managers(files, package),
                "frameworks": sorted(frameworks), "testFrameworks": sorted(tests), "fileCount": len(files)}
    supported = (unit_tests if "unittest" in tests else []) + (node_tests if "Node.js test runner" in tests else [])
    if not languages:
        review.append("Unknown language: review the project before enabling commands.")
    review.append("AI-generated draft: confirm detected languages, framework evidence and project-specific rules.")
    review.append("Generated layer permissions are permissive; review and tighten them for this architecture.")
    review.append("typeCheckCommand and dataCheckCommand remain empty until their real project commands are confirmed.")
    if not supported:
        review.append("testCommand will block changed code with noMapping until a supported targeted test mapping is confirmed.")
    elif "pytest" in tests or tests - {"unittest", "Node.js test runner"}:
        review.append("Only unittest/Node.js mappings are enabled; other test frameworks require a confirmed testCommand.")
    return {"detected": detected, "layers": layers, "review": review, "supportedTests": sorted(supported)}
