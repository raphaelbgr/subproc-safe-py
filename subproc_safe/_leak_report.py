"""Non-blocking leak reporter."""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests


class LeakReportClient:
    def __init__(self, endpoint: Optional[str] = None, enabled: bool = True):
        if endpoint is None:
            endpoint = os.environ.get("SUBPROC_SAFE_LEAK_ENDPOINT")
        self.endpoint = endpoint
        self.enabled = enabled and bool(endpoint)
        self._pool = ThreadPoolExecutor(max_workers=2)

    def report(self, event: dict) -> None:
        if not self.enabled:
            return
        self._pool.submit(self._post, event)

    def _post(self, event: dict) -> None:
        try:
            requests.post(
                self.endpoint,
                data=json.dumps(event).encode(),
                headers={"Content-Type": "application/json"},
                timeout=0.5,
            )
        except Exception:
            pass  # silent

    def close(self):
        self._pool.shutdown(wait=False)
