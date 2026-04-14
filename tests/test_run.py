import sys
import time
import pytest

from subproc_safe import run, TimeoutError as SSTimeoutError


def test_missing_timeout_raises_typeerror():
    with pytest.raises(TypeError):
        run(["echo", "hi"])  # type: ignore


def test_shell_true_banned():
    with pytest.raises(ValueError):
        run(["echo", "hi"], timeout=1, shell=True)


def test_basic_run_captures():
    cp = run([sys.executable, "-c", "print('hello')"], timeout=5)
    assert cp.returncode == 0
    assert "hello" in cp.stdout


def test_timeout_kills_tree_within_2s():
    start = time.time()
    with pytest.raises(SSTimeoutError):
        run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1)
    elapsed = time.time() - start
    assert elapsed < 3.5, f"kill took too long: {elapsed:.2f}s"


def test_check_false_returns_nonzero():
    cp = run([sys.executable, "-c", "import sys; sys.exit(7)"], timeout=5, check=False)
    assert cp.returncode == 7
