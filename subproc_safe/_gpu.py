"""GPU query via pynvml (optional dep)."""
from __future__ import annotations


class NoGPUError(Exception):
    """Raised when GPU query cannot be performed (no pynvml, no driver, or no devices)."""


def gpu_query():
    try:
        import pynvml  # type: ignore
    except ImportError as e:
        raise NoGPUError(f"pynvml not installed: {e}. Install with `pip install 'subproc-safe[gpu]'`.")

    try:
        pynvml.nvmlInit()
    except Exception as e:
        raise NoGPUError(f"nvmlInit failed: {e}")

    out = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                name = name.decode()
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            out.append({
                "index": i,
                "name": name,
                "mem_total_mb": int(mem.total // (1024 * 1024)),
                "mem_free_mb": int(mem.free // (1024 * 1024)),
                "mem_used_mb": int(mem.used // (1024 * 1024)),
                "util_gpu_pct": int(util.gpu),
                "util_mem_pct": int(util.memory),
                "temp_c": int(temp),
            })
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    return out
