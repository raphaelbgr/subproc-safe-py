import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from subproc_safe import run_cached
from subproc_safe._cache import _reset_cache_for_tests


def test_100_concurrent_calls_spawn_one_child():
    _reset_cache_for_tests()
    with tempfile.TemporaryDirectory() as d:
        cpath = os.path.join(d, "c")
        code = (
            f"import time,fcntl;p=r'{cpath}';"
            "f=open(p,'a');f.write('x');f.flush();"
            "time.sleep(0.2);print('ok')"
        )
        cmd = [sys.executable, "-c", code]

        def call():
            return run_cached(cmd, timeout=10, cache_ttl=60)

        with ThreadPoolExecutor(max_workers=100) as ex:
            results = list(ex.map(lambda _: call(), range(100)))

        assert all(r.returncode == 0 for r in results)
        assert open(cpath).read() == "x", f"expected single spawn, got {open(cpath).read()!r}"
