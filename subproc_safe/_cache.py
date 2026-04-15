"""TTL cache + single-flight wrapper."""
from __future__ import annotations

import threading
import time
from typing import Optional, Sequence, Mapping

from ._core import run


class _Entry:
    """One cache slot.

    Lifecycle
    ---------
    * ``value`` / ``expires_at`` — the durable TTL cache (success path only).
    * ``_flight`` — a ``threading.Event`` that is set when the in-flight call
      finishes (success *or* failure).  Concurrent waiters block on this event
      so they are woken up without re-spawning.
    * ``_flight_exc`` — the exception from the finished flight, if any.
      Set inside the registry lock together with ``_flight.set()`` so waiters
      read a consistent view.  Cleared at the *start* of the next flight so
      stale errors don't pollute future callers.
    """

    __slots__ = ("value", "expires_at", "_flight", "_flight_exc")

    def __init__(self):
        self.value = None
        self.expires_at = 0.0
        self._flight: Optional[threading.Event] = None
        self._flight_exc: Optional[BaseException] = None


_cache: dict[tuple, _Entry] = {}
_registry_lock = threading.Lock()


def _get_entry(key) -> _Entry:
    with _registry_lock:
        e = _cache.get(key)
        if e is None:
            e = _Entry()
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

    while True:
        with _registry_lock:
            entry = _cache.get(key)
            if entry is None:
                entry = _Entry()
                _cache[key] = entry

            now = time.time()

            # Fast path: valid cached value.
            if entry.value is not None and now < entry.expires_at:
                return entry.value

            # A flight is in progress — grab its event and wait outside the lock.
            if entry._flight is not None:
                evt = entry._flight
                # Fall through: release lock, wait on event.
            else:
                # We are the pilot.  Clear any leftover exception from a
                # previous (already settled) flight, then start a new flight.
                entry._flight_exc = None
                evt = threading.Event()
                entry._flight = evt
                pilot = True
                break  # exit while, still holding local refs

        # Waiter path — wait for the pilot to finish, then loop back.
        evt.wait()
        with _registry_lock:
            exc = entry._flight_exc
            val = entry.value
            exp = entry.expires_at
        if exc is not None:
            raise exc
        if val is not None and time.time() < exp:
            return val
        # Flight succeeded but TTL already expired, or flight cleared — retry.
        continue

    # Pilot path.
    try:
        cp = run(args, timeout=timeout, cwd=cwd, env=env, check=check, capture=capture)
        with _registry_lock:
            entry.value = cp
            entry.expires_at = time.time() + cache_ttl
            entry._flight_exc = None
            entry._flight = None
        evt.set()
        return cp
    except Exception as exc:  # noqa: BLE001
        with _registry_lock:
            entry._flight_exc = exc
            entry._flight = None
        evt.set()
        raise


def was_cached(args: Sequence[str], cwd: Optional[str] = None) -> bool:
    """Return True iff an unexpired cached entry exists for (args, cwd).

    Matches any cache_key override — returns True if ANY entry for (args, cwd)
    is unexpired, regardless of the cache_key used when storing it.
    """
    prefix_key = (tuple(args), cwd)
    now = time.time()
    with _registry_lock:
        for k, entry in _cache.items():
            if k[:2] == prefix_key and entry.value is not None and now < entry.expires_at:
                return True
    return False


def invalidate(args: Sequence[str], cwd: Optional[str] = None) -> None:
    """Drop the cached entry for (args, cwd, cache_key=None). No-op if absent."""
    key = (tuple(args), cwd, None)
    with _registry_lock:
        entry = _cache.get(key)
        if entry is not None:
            entry.value = None
            entry.expires_at = 0.0


def invalidate_prefix(arg_prefix: Sequence[str]) -> None:
    """Drop every cached entry whose argv starts with arg_prefix."""
    prefix = tuple(arg_prefix)
    n = len(prefix)
    with _registry_lock:
        for k, entry in _cache.items():
            if k[0][:n] == prefix:
                entry.value = None
                entry.expires_at = 0.0


def clear_cache() -> None:
    """Drop all cached entries. Useful in tests."""
    with _registry_lock:
        for entry in _cache.values():
            entry.value = None
            entry.expires_at = 0.0
            entry._flight_exc = None


def _reset_cache_for_tests():
    global _cache
    with _registry_lock:
        _cache = {}
