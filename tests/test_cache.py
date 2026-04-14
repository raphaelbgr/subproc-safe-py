import os
import sys
import tempfile
import time

from subproc_safe import run_cached
from subproc_safe._cache import _reset_cache_for_tests


def _counter_cmd(counter_path):
    code = (
        f"p=r'{counter_path}';"
        "open(p,'a').write('x');"
        "print('ran')"
    )
    return [sys.executable, "-c", code]


def test_cache_hit_skips_subprocess():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        cmd = _counter_cmd(cpath)
        cp1 = run_cached(cmd, timeout=5, cache_ttl=60)
        cp2 = run_cached(cmd, timeout=5, cache_ttl=60)
        assert cp1.stdout == cp2.stdout
        assert open(cpath).read() == "x"  # only one spawn


def test_ttl_expiry_respawns():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        cmd = _counter_cmd(cpath)
        run_cached(cmd, timeout=5, cache_ttl=0.1)
        time.sleep(0.2)
        run_cached(cmd, timeout=5, cache_ttl=0.1)
        assert open(cpath).read() == "xx"


def test_cache_key_override_separates_entries():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        cmd = _counter_cmd(cpath)
        run_cached(cmd, timeout=5, cache_ttl=60, cache_key="A")
        run_cached(cmd, timeout=5, cache_ttl=60, cache_key="B")
        assert open(cpath).read() == "xx"
