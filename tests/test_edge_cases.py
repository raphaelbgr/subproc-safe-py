"""Edge-case tests for subproc_safe.

Each test is self-contained. Cache-touching tests use unique cache_key values
so they never share state with other tests or each other.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from subproc_safe import run, run_cached
from subproc_safe._cache import _reset_cache_for_tests

# ---------------------------------------------------------------------------
# 1. check=True with nonzero exit raises CalledProcessError
# ---------------------------------------------------------------------------

def _exit1_cmd():
    """Cross-platform command that exits with code 1."""
    return [sys.executable, "-c", "import sys; sys.exit(1)"]


def test_check_true_nonzero_raises():
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run(_exit1_cmd(), timeout=5, check=True)
    assert exc_info.value.returncode == 1


# ---------------------------------------------------------------------------
# 2. Zero / negative timeout rejected
# ---------------------------------------------------------------------------

def test_zero_timeout_rejected():
    """timeout=0 should be rejected (or immediately expire — document behavior)."""
    # The impl passes timeout straight to subprocess.communicate(timeout=0).
    # With timeout=0, communicate raises TimeoutExpired immediately, which the
    # impl re-raises as subproc_safe.TimeoutError.  Either TimeoutError or a
    # ValueError/TypeError from the impl are acceptable — the caller must NOT
    # get a silent success with timeout=0.
    from subproc_safe import TimeoutError as SSTimeoutError

    with pytest.raises((ValueError, TypeError, SSTimeoutError)):
        run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0)


def test_negative_timeout_rejected():
    """timeout=-1 should be rejected."""
    from subproc_safe import TimeoutError as SSTimeoutError

    with pytest.raises((ValueError, TypeError, SSTimeoutError)):
        run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=-1)


# ---------------------------------------------------------------------------
# 3. Non-list args rejected
# ---------------------------------------------------------------------------

def test_string_args_rejected():
    with pytest.raises(ValueError):
        run("echo x", timeout=5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 5. cwd is respected
# ---------------------------------------------------------------------------

def test_cwd_respected():
    with tempfile.TemporaryDirectory() as d:
        # Resolve symlinks so the comparison is reliable on macOS (/var → /private/var)
        real_d = os.path.realpath(d)
        code = "import os; print(os.path.realpath(os.getcwd()))"
        cp = run([sys.executable, "-c", code], timeout=10, cwd=real_d)
        assert cp.stdout.strip() == real_d


# ---------------------------------------------------------------------------
# 6. env is respected
# ---------------------------------------------------------------------------

def test_env_respected():
    custom_env = {"FOO": "bar_unique_val_xyz", "PATH": os.environ.get("PATH", "")}
    code = "import os; print(os.environ['FOO'])"
    cp = run([sys.executable, "-c", code], timeout=10, env=custom_env)
    assert cp.stdout.strip() == "bar_unique_val_xyz"


# ---------------------------------------------------------------------------
# 7. Single-flight exception propagation
#    5 concurrent run_cached calls with check=True on a failing command.
#    All must raise; only ONE subprocess should have been spawned.
# ---------------------------------------------------------------------------

def test_single_flight_exception_propagation():
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "invocation_count")
        code = (
            f"import sys; open(r'{cpath}', 'a').write('x'); sys.exit(1)"
        )
        cmd = [sys.executable, "-c", code]

        unique_key = f"sf_exc_{id(cpath)}"

        def call_it():
            return run_cached(
                cmd,
                timeout=10,
                cache_ttl=60,
                cache_key=unique_key,
                check=True,
            )

        # Clear any previous state for this key (shouldn't matter with unique key,
        # but be safe).
        _reset_cache_for_tests()

        results = []
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(call_it) for _ in range(5)]
            for f in futures:
                try:
                    f.result()
                    results.append("ok")
                except Exception as e:
                    results.append(f"err:{type(e).__name__}")

        # All 5 must have raised
        assert all(r.startswith("err:") for r in results), (
            f"expected all errors, got: {results}"
        )

        # Only one subprocess should have been spawned
        try:
            count = len(open(cpath).read())
        except FileNotFoundError:
            # If even the file wasn't created the subprocess didn't run — that's a bug.
            pytest.fail("Counter file was never created; subprocess may not have run at all")

        assert count == 1, (
            f"expected exactly 1 subprocess invocation, got {count}"
        )


# ---------------------------------------------------------------------------
# 9. Large stdout does not deadlock
# ---------------------------------------------------------------------------

def test_large_stdout_no_deadlock():
    code = "import sys; sys.stdout.write('x' * 5_000_000)"
    cp = run([sys.executable, "-c", code], timeout=30)
    assert len(cp.stdout) >= 5_000_000
