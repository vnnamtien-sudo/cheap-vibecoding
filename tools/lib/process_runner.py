"""Shell-free subprocess execution with bounded process-tree cleanup."""
import os
import signal
import subprocess


class WindowsJob:
    """Use a Win32 job so grandchildren cannot outlive a completed command."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)

        class BasicLimits(ctypes.Structure):
            _fields_ = [("processTime", ctypes.c_longlong), ("jobTime", ctypes.c_longlong), ("flags", wintypes.DWORD),
                        ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t), ("active", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("readOps", "writeOps", "otherOps", "readBytes", "writeBytes", "otherBytes")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", IoCounters), ("processMemory", ctypes.c_size_t),
                        ("jobMemory", ctypes.c_size_t), ("peakProcess", ctypes.c_size_t), ("peakJob", ctypes.c_size_t)]

        self.kernel.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        self.kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        self.kernel.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
        self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign_and_resume(self, process):
        ctypes, wintypes, kernel = self.ctypes, self.wintypes, self.kernel
        if not kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())

        class ThreadEntry(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("thread", wintypes.DWORD),
                        ("owner", wintypes.DWORD), ("priority", wintypes.LONG), ("delta", wintypes.LONG), ("flags", wintypes.DWORD)]

        kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.Thread32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(ThreadEntry))
        kernel.Thread32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(ThreadEntry))
        kernel.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenThread.restype = wintypes.HANDLE
        kernel.ResumeThread.argtypes = (wintypes.HANDLE,)
        kernel.ResumeThread.restype = wintypes.DWORD
        snapshot = kernel.CreateToolhelp32Snapshot(4, 0)
        if snapshot == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        resumed = False
        try:
            entry = ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found = kernel.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.owner == process.pid:
                    thread = kernel.OpenThread(2, False, entry.thread)
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        previous = kernel.ResumeThread(thread)
                        resumed = 0 < previous < 0xFFFFFFFF
                    finally:
                        kernel.CloseHandle(thread)
                    if resumed:
                        break
                found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
        if not resumed:
            raise OSError("could not resume the child after assigning its process-tree job")

    def kill(self):
        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 124)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def kill_tree(process, job=None):
    if job:
        job.kill()
    elif os.name == "posix":
        # shortcut: process groups cannot contain descendants that deliberately call setsid().
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            # macOS answers EPERM once only zombies are left in the group; callers still kill a live leader.
            pass
    elif process.poll() is None:
        process.kill()


def _drain(process, job):
    kill_tree(process, job)
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired as error:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        return error.output, error.stderr


def run_command(argv, *, cwd=None, timeout=900, capture_output=False, text=True, input=None, env=None):
    """Return CompletedProcess; on timeout kill the tree, then raise TimeoutExpired.

    Windows starts suspended until the job assignment succeeds. A denied job assignment
    fails closed. POSIX uses a fresh process group; intentional daemon escape is outside
    the guarantee. Both success and failure close any remaining descendants.
    """
    if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(value, (str, os.PathLike)) for value in argv):
        raise ValueError("command must be a nonempty argv array")
    job, process = None, None
    options = dict(cwd=cwd, env=env, shell=False, text=text)
    if capture_output:
        options.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if input is not None:
        options["stdin"] = subprocess.PIPE
    try:
        if os.name == "nt":
            job = WindowsJob()
            options["creationflags"] = 0x4  # CREATE_SUSPENDED: no child-spawn race before job assignment.
        else:
            options["start_new_session"] = True
        process = subprocess.Popen(argv, **options)
        if job:
            job.assign_and_resume(process)
        try:
            stdout, stderr = process.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            stdout, stderr = _drain(process, job)
            raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr) from None
        except BaseException:
            _drain(process, job)
            raise
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        if process:
            kill_tree(process, job)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        if job:
            job.close()
