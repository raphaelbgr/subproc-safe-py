import os
import sys
import tempfile
import time

from subproc_safe import run_cached, was_cached, invalidate, invalidate_prefix, clear_cache
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


# ---------------------------------------------------------------------------
# Cache helper tests
# ---------------------------------------------------------------------------

def test_was_cached_true_after_run():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        cmd = _counter_cmd(cpath)
        assert not was_cached(cmd)
        run_cached(cmd, timeout=5, cache_ttl=60)
        assert was_cached(cmd)


def test_was_cached_false_after_expiry():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        cmd = _counter_cmd(cpath)
        run_cached(cmd, timeout=5, cache_ttl=0.1)
        time.sleep(0.2)
        assert not was_cached(cmd)


def test_invalidate_drops_entry():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        cmd = _counter_cmd(cpath)
        run_cached(cmd, timeout=5, cache_ttl=60)
        assert was_cached(cmd)
        invalidate(cmd)
        assert not was_cached(cmd)
        # Next call re-spawns
        run_cached(cmd, timeout=5, cache_ttl=60)
        assert open(cpath).read() == "xx"


def test_invalidate_prefix_drops_matching_entries():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath1 = os.path.join(d, "c1")
        cpath2 = os.path.join(d, "c2")
        cmd1 = _counter_cmd(cpath1)
        cmd2 = _counter_cmd(cpath2)
        run_cached(cmd1, timeout=5, cache_ttl=60)
        run_cached(cmd2, timeout=5, cache_ttl=60)
        assert was_cached(cmd1)
        assert was_cached(cmd2)
        # Both commands start with sys.executable — bust all python entries
        invalidate_prefix([sys.executable])
        assert not was_cached(cmd1)
        assert not was_cached(cmd2)


def test_clear_cache_drops_all():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        cmd = _counter_cmd(cpath)
        run_cached(cmd, timeout=5, cache_ttl=60)
        assert was_cached(cmd)
        clear_cache()
        assert not was_cached(cmd)
