"""TTL cache + single-flight wrapper."""
from __future__ import annotations

import threading
import time
from typing import Optional, Sequence, Mapping

from ._core import run


class _Entry:
    __slots__ = ("value", "expires_at", "lock")

    def __init__(self, lock):
        self.value = None
        self.expires_at = 0.0
        self.lock = lock


_cache: dict = {}
_registry_lock = threading.Lock()


def _get_entry(key):
    with _registry_lock:
        e = _cache.get(key)
        if e is None:
            e = _Entry(threading.Lock())
            _cache[key] = e
        return e


def run_cached(
    args: Sequence[str],
    *,
    timeout,
    cache_ttl: float,
    cache_key: Optional[str] = None,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    check: bool = True,
    capture: bool = True,
):
    key = (tuple(args), cwd, cache_key)
    entry = _get_entry(key)

    now = time.time()
    if entry.value is not None and now < entry.expires_at:
        return entry.value

    with entry.lock:
        now = time.time()
        if entry.value is not None and now < entry.expires_at:
            return entry.value
        cp = run(args, timeout=timeout, cwd=cwd, env=env, check=check, capture=capture)
        entry.value = cp
        entry.expires_at = time.time() + cache_ttl
        return cp


def _reset_cache_for_tests():
    global _cache
    with _registry_lock:
        _cache = {}
