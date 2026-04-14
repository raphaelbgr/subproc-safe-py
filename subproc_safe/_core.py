"""Core run() with mandatory timeout + process-tree kill."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Optional, Sequence, Mapping

import psutil

_SENTINEL = object()


class TimeoutError(Exception):
    """Raised when a subprocess exceeds its timeout and has been tree-killed."""


class LeakError(Exception):
    """Raised for leak-reporting related errors (reserved; not normally raised)."""


def _kill_tree(pid: int) -> None:
    """Terminate then kill pid and all descendants. Cross-platform."""
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    try:
        descendants = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        descendants = []

    procs = descendants + [parent]

    # Graceful
    for p in procs:
        try:
            if sys.platform == "win32":
                p.terminate()
            else:
                p.send_signal(signal.SIGTERM)
        except psutil.NoSuchProcess:
            pass

    gone, alive = psutil.wait_procs(procs, timeout=1.0)

    # Force
    for p in alive:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=1.0)


def run(
    args: Sequence[str],
    *,
    timeout=_SENTINEL,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    check: bool = True,
    capture: bool = True,
    shell: bool = False,
    _leak_client: "Optional[object]" = None,
) -> subprocess.CompletedProcess:
    """Safe subprocess.run wrapper.

    timeout is kwarg-only and REQUIRED.
    shell=True is banned (ValueError).
    """
    if shell:
        raise ValueError("shell=True is banned in subproc_safe.run()")
    if timeout is _SENTINEL:
        raise TypeError("run() missing required keyword-only argument: 'timeout'")
    if not isinstance(args, (list, tuple)):
        raise ValueError("args must be a list or tuple; string args (shell=True style) are banned")

    stdout = subprocess.PIPE if capture else None
    stderr = subprocess.PIPE if capture else None

    started = time.time()
    proc = subprocess.Popen(
        list(args),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=stdout,
        stderr=stderr,
        text=True,
        shell=False,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            out, err = proc.communicate(timeout=2.0)
        except Exception:
            out, err = "", ""
        duration = time.time() - started
        if _leak_client is not None:
            try:
                _leak_client.report({
                    "caller": _caller_hint(),
                    "args": list(args),
                    "pid": proc.pid,
                    "cwd": cwd or os.getcwd(),
                    "started_at": started,
                    "duration_s": duration,
                    "exit_code": None,
                })
            except Exception:
                pass
        raise TimeoutError(f"command timed out after {timeout}s: {list(args)}")

    duration = time.time() - started
    cp = subprocess.CompletedProcess(args=list(args), returncode=proc.returncode, stdout=out, stderr=err)

    if _leak_client is not None:
        try:
            _leak_client.report({
                "caller": _caller_hint(),
                "args": list(args),
                "pid": proc.pid,
                "cwd": cwd or os.getcwd(),
                "started_at": started,
                "duration_s": duration,
                "exit_code": proc.returncode,
            })
        except Exception:
            pass

    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, list(args), output=out, stderr=err)
    return cp


def _caller_hint() -> str:
    import inspect
    try:
        frame = inspect.stack()[2]
        return f"{frame.filename}:{frame.lineno}"
    except Exception:
        return "unknown"


def _reject_shell(**kwargs):
    if kwargs.get("shell"):
        raise ValueError("shell=True is banned in subproc_safe.run()")
