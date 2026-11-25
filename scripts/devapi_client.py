#!/usr/bin/env python3
"""Minimal Developer-API client for container hosts.

Handles the two things that break naive calls: the mandatory Idempotency-Key on writes and
429/503/409 backoff via Retry-After.

Library:
    from devapi_client import call
    st, out = call("GET", "/workloads")
    st, out = call("PUT", f"/workloads/{wid}/env", {"key": "K", "value": "V", "isSecret": True}, idem=True)

CLI:
    DEVAPI_BASE=https://api.example.com/api/v1/developer DEVAPI_KEY=~/.secrets/devapi.key \
      python3 devapi_client.py GET /workloads
"""
import json, os, sys, time, uuid, urllib.request, urllib.error

BASE = os.environ.get("DEVAPI_BASE", "").rstrip("/")
KEY = open(os.environ.get("DEVAPI_KEY", os.path.expanduser("~/.secrets/devapi.key"))) \
    .read().splitlines()[0].strip()


def call(method: str, path: str, body=None, idem: bool = False, tries: int = 8):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        h = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json",
             "Accept": "application/json"}
        if idem:
            h["Idempotency-Key"] = uuid.uuid4().hex
        req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            wait = e.headers.get("Retry-After")
            wait = int(wait) if wait and wait.isdigit() else min(5 * (i + 1), 40)
            if e.code in (429, 503, 409) and i < tries - 1:
                print(f"retry {e.code} after {wait}s", flush=True)
                time.sleep(wait)
                continue
            return e.code, raw


if __name__ == "__main__":
    if len(sys.argv) < 3 or not BASE:
        print(__doc__)
        raise SystemExit(2)
    st, out = call(sys.argv[1].upper(), sys.argv[2])
    print(st, json.dumps(out, indent=2)[:4000] if not isinstance(out, str) else out[:4000])
