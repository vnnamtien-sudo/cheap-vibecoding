"""Bounded Git input collection and index snapshot support."""
import os
from pathlib import Path, PurePosixPath
import subprocess


CODE_EXTENSIONS = frozenset({
    ".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx", ".py", ".pyi", ".java", ".kt",
    ".go", ".rs", ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp", ".swift",
    ".ps1", ".cmd", ".bat", ".sh", ".sql", ".css", ".scss", ".vue", ".svelte",
})


def git(root, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(["git", *args], cwd=str(root), env=env, shell=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError("git {} failed: {}".format(args[0], result.stderr.decode("utf-8", "replace").strip()))
    return result.stdout


def project_root(selected=None):
    root = Path(selected or Path.cwd()).resolve()
    if not root.is_dir():
        raise ValueError("Project root is not a directory: {}".format(root))
    if selected is not None:
        return root
    try:
        return Path(git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    except (OSError, ValueError, UnicodeError):
        return root


def safe_relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe Git path: {!r}".format(name))
    return path


def changed_names(root, staged=False):
    # NUL records preserve spaces, newlines and non-ASCII names without shell parsing.
    calls = [("diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z", "--")]
    if not staged:
        calls.extend([("diff", "--name-only", "--diff-filter=ACMRT", "-z", "--"),
                      ("ls-files", "--others", "--exclude-standard", "-z", "--")])
    names = set()
    for args in calls:
        for raw in git(root, *args).split(b"\x00"):
            if raw:
                name = raw.decode("utf-8", "strict")
                safe_relative(name)
                if not name.startswith(".ai-gates/"):  # init 生成的辅助脚本，不算改动
                    names.add(name)
    return sorted(names)


def read_changed(root, names, staged=False):
    files = {}
    ignored = []
    for name in names:
        path = root / name
        if staged:
            mode = git(root, "ls-files", "--stage", "--", name).split(b" ", 1)[0]
            if mode == b"120000":
                raise ValueError("Changed symbolic links are unsupported: {}".format(name))
            data = git(root, "show", ":" + name)
        else:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("Changed linked file escapes safe input: {}".format(name))
            if not path.is_file():
                ignored.append({"file": name, "reason": "deleted or not a regular file"})
                continue
            data = path.read_bytes()
        try:
            if b"\x00" in data:
                raise UnicodeError("binary NUL byte")
            files[name] = data.decode("utf-8-sig")
        except UnicodeError:
            if Path(name).suffix.lower() in CODE_EXTENSIONS:
                raise ValueError("Changed code file is binary or not UTF-8: {}".format(name)) from None
            ignored.append({"file": name, "reason": "binary or non-UTF-8 text"})
    return files, ignored


def create_index_snapshot(root, destination):
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\x00"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        safe_relative(name.decode("utf-8", "strict"))
        if metadata.split(b" ", 1)[0] in (b"120000", b"160000"):
            raise ValueError("Index snapshot cannot execute linked files or submodules")
    prefix = str(destination.resolve()) + os.sep
    git(root, "checkout-index", "--all", "--prefix=" + prefix)
    return destination
