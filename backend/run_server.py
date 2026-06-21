"""
ElderBridge GuardianOS — local network dev/demo server launcher.

Run this script (from the backend/ directory) to start the API on all
network interfaces so Android devices on the same WiFi can reach it:

    python run_server.py

The script prints the LAN IP address so you know which URL to give the
Android app, e.g.:

    [ElderBridge] Server running at http://192.168.1.42:8000
    [ElderBridge] API docs at        http://192.168.1.42:8000/docs
    [ElderBridge] POST endpoint:     http://192.168.1.42:8000/analyze-event

Security note: this launcher binds to 0.0.0.0 (all interfaces).
Do NOT use it on an untrusted or public network — it is for local
development and demo use only.  Production deployment requires a proper
reverse proxy (nginx/Caddy) with TLS and firewall rules.

Environment:
  ANTHROPIC_API_KEY must be set in .env (or the shell) before running,
  otherwise BenefitsAgent will raise RuntimeError on the first request.
"""
from __future__ import annotations

import os
import socket
import sys

# Ensure backend/ package imports resolve when run as `python run_server.py`
sys.path.insert(0, os.path.dirname(__file__))

PORT = 8000


def _local_ip() -> str:
    """Return the machine's LAN IP by probing an outbound route.

    Does not send any data — the socket is immediately closed.
    Falls back to 127.0.0.1 if no network is available.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))   # routable address — no data sent
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    import uvicorn

    ip = _local_ip()
    base = f"http://{ip}:{PORT}"

    print()
    print(f"[ElderBridge] Server running at  {base}")
    print(f"[ElderBridge] API docs at         {base}/docs")
    print(f"[ElderBridge] POST endpoint:      {base}/analyze-event")
    print(f"[ElderBridge] Health check:       {base}/health")
    print()
    print("  Give the Android app this base URL:")
    print(f"    BASE_URL = \"{base}\"")
    print()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level=os.environ.get("LOG_LEVEL", "info"),
        # reload=False — singleton graph must not be rebuilt between reloads
    )
