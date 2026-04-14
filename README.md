# subproc-safe

Safe subprocess wrapper for Python. Always-timeout, always tree-kill, TTL cache + single-flight, optional GPU query, non-blocking leak reporting.

## Install

```
pip install subproc-safe           # core
pip install 'subproc-safe[gpu]'    # + pynvml for gpu_query()
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
