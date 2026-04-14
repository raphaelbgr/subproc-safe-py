import sys
import types
import importlib
import pytest


def test_no_pynvml_raises_nogpuerror(monkeypatch):
    # Simulate pynvml missing
    monkeypatch.setitem(sys.modules, "pynvml", None)
    import subproc_safe._gpu as g
    importlib.reload(g)
    with pytest.raises(g.NoGPUError):
        g.gpu_query()


def test_present_pynvml_returns_well_shaped(monkeypatch):
    fake = types.ModuleType("pynvml")

    class _Mem:
        total = 8 * 1024 * 1024 * 1024
        free = 4 * 1024 * 1024 * 1024
        used = 4 * 1024 * 1024 * 1024

    class _Util:
        gpu = 42
        memory = 17

    fake.NVML_TEMPERATURE_GPU = 0
    fake.nvmlInit = lambda: None
    fake.nvmlShutdown = lambda: None
    fake.nvmlDeviceGetCount = lambda: 1
    fake.nvmlDeviceGetHandleByIndex = lambda i: object()
    fake.nvmlDeviceGetName = lambda h: "FakeGPU 9000"
    fake.nvmlDeviceGetMemoryInfo = lambda h: _Mem()
    fake.nvmlDeviceGetUtilizationRates = lambda h: _Util()
    fake.nvmlDeviceGetTemperature = lambda h, t: 55

    monkeypatch.setitem(sys.modules, "pynvml", fake)
    import subproc_safe._gpu as g
    importlib.reload(g)
    out = g.gpu_query()
    assert len(out) == 1
    d = out[0]
    for k in ("index", "name", "mem_total_mb", "mem_free_mb", "mem_used_mb",
              "util_gpu_pct", "util_mem_pct", "temp_c"):
        assert k in d
    assert d["name"] == "FakeGPU 9000"
    assert d["mem_total_mb"] == 8192
    assert d["util_gpu_pct"] == 42
    assert d["temp_c"] == 55
