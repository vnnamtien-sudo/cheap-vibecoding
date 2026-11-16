#!/usr/bin/env python3
"""Run targeted tests with a timeout; opt into the shared pool with mode=advanced."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.lib.gate_config import load_config
from tools.lib.process_runner import run_command


def _resolve(root, value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(root) / path


def queue_config(root, config_path=None):
    config = dict(load_config(root, config_path=config_path).get("testQueue", {}))
    config["_root"] = str(root)
    config["dataPath"] = _resolve(root, config.get("dataDir", ".gate/test-queue"))
    return config


def classify(command, cwd, config):
    text = " ".join(command)
    tokens = [str(part) for part in command]
    heavy, runner, targets = False, None, []
    if "-m" in tokens:
        index = tokens.index("-m") + 1
        if index < len(tokens) and tokens[index] in ("unittest", "pytest"):
            runner, targets = tokens[index], tokens[index + 1:]
    executable = Path(tokens[0]).stem.lower() if tokens else ""
    if executable in ("pytest", "py.test", "jest", "vitest"):
        runner, targets = executable, tokens[1:]
    elif "--test" in tokens:
        runner, targets = "node", tokens[tokens.index("--test") + 1:]
    elif executable in ("npm", "pnpm", "yarn") and "test" in tokens:
        runner, targets = "npm", tokens[tokens.index("test") + 1:]
    elif executable in ("go", "cargo") and "test" in tokens:
        runner, targets = executable, tokens[tokens.index("test") + 1:]
    if runner:
        concrete = any(not part.startswith("-") and part not in ("discover", ".", "tests", "test", "./...", "...")
                       and ("." in part or "::" in part) and not (Path(cwd) / part).is_dir() for part in targets)
        selector = any(part in ("-k", "--keyword", "-run", "--testNamePattern", "-t") for part in targets)
        heavy = not (concrete or selector)
        if runner == "unittest" and "discover" in targets:
            heavy = True
    heavy = heavy or any(re.search(pattern, text) for pattern in config.get("heavyPatterns", []))
    weight = 1
    if config.get("mode", "targeted") == "advanced":
        match = re.search(config.get("workerPattern") or r"(?:-n|--numprocesses|--workers)(?:=|\s+)(\d+|auto)\b", text)
        if match:
            weight = int(match.group(1)) if match.group(1).isdigit() else config.get("autoWeight", 4)
        weight = min(config.get("slots", 20), max(1, weight))
    return {"heavy": bool(heavy), "weight": weight}


def alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            return kernel.WaitForSingleObject(handle, 0) == 0x102
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _paths(config):
    root = Path(config["dataPath"])
    root.mkdir(parents=True, exist_ok=True)
    return root / "state.json", root / ".lock", root / "runs.jsonl"


def release_lock(lock):
    deadline = time.monotonic() + 1
    while True:
        try:
            (lock / "owner.json").unlink(missing_ok=True)
            lock.rmdir()
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


@contextmanager
def locked_state(config):
    state_file, lock, _ = _paths(config)
    deadline = time.monotonic() + 15
    while True:
        try:
            lock.mkdir()
            (lock / "owner.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 10:
                    owner = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
                    if not alive(owner.get("pid")):
                        release_lock(lock)
                        continue
            except (OSError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("test-queue lock busy; check the lock owner before recovery")
            time.sleep(0.02)
    try:
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {"holders": [], "waiters": []}
        if not isinstance(state, dict) or not isinstance(state.get("holders"), list) or not isinstance(state.get("waiters"), list):
            raise ValueError("invalid queue state; preserve it and recover before running more tests")
        yield state
        temporary = state_file.with_name("state.%s.%s.tmp" % (os.getpid(), uuid.uuid4().hex))
        try:
            temporary.write_text(json.dumps(state, ensure_ascii=True), encoding="utf-8")
            os.replace(str(temporary), str(state_file))
        finally:
            if temporary.exists():
                temporary.unlink()
    finally:
        release_lock(lock)


def clean(state, config, now=None):
    now = time.time() * 1000 if now is None else now
    stale = config.get("staleMinutes", 20) * 60000
    state["holders"] = [holder for holder in state["holders"] if alive(holder.get("pid"))]
    state["waiters"] = [waiter for waiter in state["waiters"] if alive(waiter.get("pid")) and now - waiter.get("seen", waiter.get("since", 0)) < stale]


def used(state):
    return sum(holder.get("weight", 1) for holder in state["holders"])


def session_dirs_of(config):
    if isinstance(config.get("sessionDirs"), list):
        return config["sessionDirs"]
    result = []
    for agent, roots in config.get("sessionRoots", {}).items():
        for root in [roots] if isinstance(roots, str) else roots:
            result.append({"path": root, "ext": ".json" if agent == "gemini" else ".jsonl",
                           "depth": {"claude": 2, "deepseek": 2, "codex": 4, "gemini": 3}.get(agent, 1)})
    if config.get("transcriptsRoot"):
        result.append({"path": config["transcriptsRoot"], "ext": ".jsonl", "depth": 2})
    return result


def _count_fresh(root, extension, depth, cutoff):
    count = 0
    try:
        for path in root.iterdir():
            if depth > 1 and path.is_dir() and not path.is_symlink():
                count += _count_fresh(path, extension, depth - 1, cutoff)
            elif depth == 1 and path.is_file() and path.name.endswith(extension) and path.stat().st_mtime >= cutoff:
                count += 1
    except OSError:
        pass
    return count


def active_sessions(config, now=None):
    if config.get("mode", "targeted") != "advanced" or config.get("poolCountsSessions", True) is False:
        return 0
    now = time.time() if now is None else now
    cutoff, count = now - config.get("activeSessionMinutes", 10) * 60, 0
    for descriptor in session_dirs_of(config):
        root = _resolve(config.get("_root", Path.cwd()), descriptor["path"])
        depth, extension = max(1, int(descriptor.get("depth", 1))), descriptor.get("ext", ".jsonl")
        if descriptor.get("datedDays") and depth >= 4:
            for offset in range(int(descriptor["datedDays"])):
                date = datetime.fromtimestamp(now, timezone.utc) - timedelta(days=offset)
                count += _count_fresh(root / date.strftime("%Y/%m/%d"), extension, depth - 3, cutoff)
        else:
            count += _count_fresh(root, extension, depth, cutoff)
    return count


def free_memory():
    try:
        if os.name != "nt":
            return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(name, ctypes.c_ulonglong) for name in
                ("totalPhys", "availPhys", "totalPage", "availPage", "totalVirtual", "availVirtual", "availExtended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        return status.availPhys if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
    except (OSError, ValueError, AttributeError):
        return None


def test_limit(config, state, active, free_bytes=None):
    minimum = config.get("minTestSlots", 1)
    limit = max(minimum, config.get("slots", 20) - max(0, active - len(state["holders"]) - len(state["waiters"])))
    if free_bytes is not None and free_bytes < config.get("minFreeGB", 0) * 2 ** 30:
        limit = min(limit, used(state))
    return limit


def can_grant(state, waiter, limit):
    occupied = used(state)
    return occupied + waiter["weight"] <= limit or occupied == 0


def head_of(state, config):
    full = sum(bool(holder.get("heavy")) for holder in state["holders"]) >= config.get("heavyMax", 1)
    return next((waiter for waiter in state["waiters"] if not (waiter.get("heavy") and full)), None)


def execute(command, timeout_seconds):
    try:
        result = run_command(command, timeout=timeout_seconds)
        return result.returncode, "pass" if result.returncode == 0 else "fail"
    except subprocess.TimeoutExpired:
        print("test-queue: timeout; the child process tree was terminated", file=sys.stderr)
        return 124, "timeout"
    except KeyboardInterrupt:
        return 130, "interrupted"
    except OSError as error:
        print("test-queue: " + str(error), file=sys.stderr)
        return 127, "command_error"


def _release(config, identity):
    with locked_state(config) as state:
        state["holders"] = [holder for holder in state["holders"] if holder["id"] != identity]
        state["waiters"] = [waiter for waiter in state["waiters"] if waiter["id"] != identity]


def acquire(config, ticket):
    with locked_state(config) as state:
        clean(state, config)
        state["waiters"].append(ticket)
    noted = 0
    while True:
        active, memory, granted = active_sessions(config), free_memory(), False
        with locked_state(config) as state:
            clean(state, config)
            waiter = next((item for item in state["waiters"] if item["id"] == ticket["id"]), None)
            if waiter is None:
                state["waiters"].append(ticket)
                waiter = ticket
            waiter["seen"] = time.time() * 1000
            head = head_of(state, config)
            limit = test_limit(config, state, active, memory)
            if head and head["id"] == ticket["id"] and can_grant(state, ticket, limit):
                state["waiters"] = [item for item in state["waiters"] if item["id"] != ticket["id"]]
                state["holders"].append(dict(ticket, startedAt=time.time() * 1000))
                granted = True
            elif time.monotonic() - noted > 60:
                noted = time.monotonic()
                print("test-queue: waiting (%s/%s test slots used)" % (used(state), limit), file=sys.stderr)
        if granted:
            return
        time.sleep(config.get("pollMs", 2000) / 1000)


def cmd_run(args, config):
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise ValueError("run needs -- followed by command arguments")
    classification = classify(command, Path.cwd(), config)
    advanced = config.get("mode", "targeted") == "advanced"
    if classification["heavy"] and (not advanced or (config.get("heavyOnlyLabels", False) and not re.search(config.get("heavyLabels", "merge|verify|nightly"), args.label, re.I))):
        raise ValueError("run targeted test files/cases; full-suite runs require an authorized advanced configuration and label")
    if args.weight is not None:
        if not advanced or args.weight < 1:
            raise ValueError("--weight is positive and available only in advanced mode")
        classification["weight"] = min(config.get("slots", 20), args.weight)
    started = time.monotonic()
    ticket = dict(classification, id=uuid.uuid4().hex, pid=os.getpid(), label=args.label,
                  since=time.time() * 1000, cmd=shlex.join(command)[:300])
    try:
        if advanced:
            acquire(config, ticket)
        wait_ms = round((time.monotonic() - started) * 1000)
        run_start = time.monotonic()
        code, outcome = execute(command, config.get("timeoutSeconds", 900))
        record = dict(at=datetime.now(timezone.utc).isoformat(), label=args.label, argv=command, cmd=ticket["cmd"],
                      weight=ticket["weight"], heavy=ticket["heavy"], waitMs=wait_ms,
                      runMs=round((time.monotonic() - run_start) * 1000), outcome=outcome, exitCode=code)
        with _paths(config)[2].open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=True) + "\n")
        return code
    finally:
        if advanced:
            _release(config, ticket["id"])


def cmd_status(config, as_json=False):
    advanced = config.get("mode", "targeted") == "advanced"
    result = {"mode": "advanced" if advanced else "targeted", "timeoutSeconds": config.get("timeoutSeconds", 900)}
    if advanced:
        active, memory = active_sessions(config), free_memory()
        with locked_state(config) as state:
            clean(state, config)
            result.update(slots=config.get("slots", 20), activeSessions=active,
                          testSlots=test_limit(config, state, active, memory), used=used(state),
                          freeBytes=memory, holders=list(state["holders"]), waiters=list(state["waiters"]))
    print(json.dumps(result, ensure_ascii=True) if as_json else str(result))
    return 0


def cmd_stats(config, days=7, as_json=False):
    rows, invalid = [], 0
    path = Path(config["dataPath"]) / "runs.jsonl"
    if path.exists():
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    at = datetime.fromisoformat(row["at"].replace("Z", "+00:00")).timestamp()
                    if at >= time.time() - days * 86400:
                        rows.append(row)
                except (ValueError, TypeError, KeyError):
                    invalid += 1
    long = [row for row in rows if row["waitMs"] + row["runMs"] > 600000]
    result = {"days": days, "runs": len(rows), "over10min": len(long),
              "waitingDominated": sum(row["waitMs"] >= row["runMs"] for row in long),
              "timeouts": sum(row["outcome"] == "timeout" for row in rows), "heavy": sum(bool(row["heavy"]) for row in rows), "invalidLogLines": invalid}
    print(json.dumps(result, ensure_ascii=True) if as_json else str(result))
    return 0


def interrupt_handler(_signal, _frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config")
    subparsers = parser.add_subparsers(dest="action", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--label", default="unlabeled")
    run.add_argument("--weight", type=int)
    run.add_argument("command", nargs=argparse.REMAINDER)
    status = subparsers.add_parser("status")
    status.add_argument("--json", action="store_true")
    stats = subparsers.add_parser("stats")
    stats.add_argument("--days", type=float, default=7)
    stats.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    config = queue_config(args.root, args.config)
    previous = None
    if hasattr(signal, "SIGTERM"):
        previous = signal.signal(signal.SIGTERM, interrupt_handler)
    try:
        if args.action == "run":
            return cmd_run(args, config)
        if args.action == "status":
            return cmd_status(config, args.json)
        if args.days <= 0:
            raise ValueError("--days must be positive")
        return cmd_stats(config, args.days, args.json)
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, RuntimeError, TypeError) as error:
        print("test-queue: " + str(error), file=sys.stderr)
        sys.exit(2)
