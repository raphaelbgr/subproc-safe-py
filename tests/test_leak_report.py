import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from subproc_safe import LeakReportClient


def test_swallows_connection_refused():
    # No server on this port — post should fail silently
    c = LeakReportClient(endpoint="http://127.0.0.1:1/leak", enabled=True)
    c.report({"caller": "test", "args": ["x"], "pid": 0, "cwd": "/", "started_at": 0, "duration_s": 0, "exit_code": 0})
    time.sleep(0.6)  # give fire-and-forget thread time to fail
    c.close()


def test_successful_post_sends_expected_shape():
    received = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n)
            received.append(json.loads(body))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        c = LeakReportClient(endpoint=f"http://127.0.0.1:{port}/leak", enabled=True)
        event = {
            "caller": "t.py:1",
            "args": ["echo", "hi"],
            "pid": 123,
            "cwd": "/tmp",
            "started_at": 1.0,
            "duration_s": 0.05,
            "exit_code": 0,
        }
        c.report(event)

        for _ in range(20):
            if received:
                break
            time.sleep(0.1)
        c.close()
        assert len(received) == 1
        assert received[0] == event
    finally:
        srv.shutdown()
