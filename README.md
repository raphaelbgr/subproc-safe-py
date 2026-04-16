# subproc-safe

Safe subprocess wrapper for Python. Always-timeout, always tree-kill, TTL cache + single-flight, optional GPU query, non-blocking leak reporting.

## Install

```
pip install subproc-safe           # core
pip install 'subproc-safe[gpu]'    # + pynvml for gpu_query()
```

### Install via git URL (no PyPI account required)

Not published to PyPI. Pin to a git tag for reproducibility.

```
pip install "subproc-safe @ git+https://github.com/raphaelbgr/subproc-safe-py.git@v0.1.1"
```

## Usage

```python
from subproc_safe import run, run_cached, gpu_query, LeakReportClient

cp = run(["echo", "hi"], timeout=5)           # timeout is REQUIRED
cp = run_cached(["slow-cmd"], timeout=30, cache_ttl=60)

for g in gpu_query():
    print(g["name"], g["mem_free_mb"])

client = LeakReportClient(endpoint="http://localhost:9999/leak")
```

## Why

- `timeout` is mandatory — no accidental forever-hangs.
- On timeout, the whole descendant process tree is killed (SIGTERM → 1s → SIGKILL), not just the direct child.
- `shell=True` is banned.
- `run_cached` coalesces concurrent identical calls to a single subprocess via mutex + TTL cache.
- `LeakReportClient` fire-and-forgets POSTs to a central endpoint; never blocks, never raises.

## Rules enforced

Origin: [avell-i7 2026-04-14 subprocess-leak postmortem](https://github.com/raphaelbgr/subproc-safe-py).

| # | Rule | Enforcement |
|---|------|-------------|
| 1 | **Mandatory timeout** — every call must specify a timeout; no accidental forever-hangs. | **LIB** — `run()` raises `TypeError` if `timeout` is absent or `None`. |
| 2 | **Windows console suppress** — `CREATE_NO_WINDOW + STARTF_USESHOWWINDOW SW_HIDE` prevents flash windows from headless parents. | **LIB** — injected automatically on `win32`; no-op on POSIX. |
| 3 | **TTL cache + single-flight** — repeated identical calls within a TTL window collapse into one subprocess. | **LIB** — `run_cached(cmd, timeout=..., cache_ttl=...)`. |
| 4 | **Prefer in-process bindings** — native Python bindings (`ctypes`, `cffi`, SDK clients) are always faster and safer than forking. | **CALLER** — document the choice; use `run()` only when no binding exists. |
| 5 | **Single-instance lock per service** — prevent duplicate daemon spawns with a pid-file or advisory lock. | **CALLER** — out of library scope; implement in your service entrypoint. |
| 6 | **One chokepoint wrapper per service** — all subprocesses for a service flow through a single call site. | **LIB** — this library *is* that chokepoint; import it everywhere instead of calling `subprocess` directly. |
| 7 | **SSH multiplexing** — reuse `ControlMaster` connections to avoid per-command TCP handshakes. | **INFRA** — configure in `~/.ssh/config`; out of library scope. |
