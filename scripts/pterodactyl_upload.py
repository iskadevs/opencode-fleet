#!/usr/bin/env python3
"""Bulk-upload a local tree into a Pterodactyl server via the client API.

Paths under --roots are RELATIVE TO THE SERVER ROOT ("/" == the egg working directory).
Absolute /home/... paths are refused: the panel would silently nest them under home/... and
nothing would ever read the files.

Usage:
  python3 pterodactyl_upload.py --panel https://panel.example.com --server <uuid> \
      --key ~/.secrets/panel.key --src ./skills --roots /config/skills
"""
import argparse, os, sys, time, urllib.parse, urllib.request, urllib.error

# Many panels sit behind a WAF that 403s python-urllib with "error code: 1010".
UA = "curl/8.5.0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True, help="e.g. https://panel.example.com/api/client")
    ap.add_argument("--server", required=True)
    ap.add_argument("--key", default=os.path.expanduser("~/.secrets/panel.key"))
    ap.add_argument("--src", required=True)
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--delay", type=float, default=0.4)
    a = ap.parse_args()

    for r in a.roots:
        if r.startswith("/home/"):
            sys.exit(f"refusing absolute data path {r!r}: use server-root-relative paths")

    key = open(a.key).read().splitlines()[0].strip()
    base = f"{a.panel.rstrip('/')}/servers/{a.server}/files/write"

    files = []
    for dirpath, _, names in os.walk(a.src):
        for n in names:
            p = os.path.join(dirpath, n)
            files.append((os.path.relpath(p, a.src), open(p, "rb").read()))
    print(f"files {len(files)} bytes {sum(len(b) for _, b in files)}", flush=True)

    t0, fails = time.time(), 0
    for root in a.roots:
        for rel, data in files:
            url = base + "?file=" + urllib.parse.quote(root + "/" + rel, safe="")
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "Authorization": "Bearer " + key, "User-Agent": UA,
                "Content-Type": "application/octet-stream"})
            try:
                urllib.request.urlopen(req, timeout=120).read()
            except urllib.error.HTTPError as e:
                fails += 1
                print("FAIL", e.code, root + "/" + rel, e.read()[:120], flush=True)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("ERR", root + "/" + rel, e, flush=True)
            time.sleep(a.delay)
    print(f"elapsed {time.time() - t0:.0f}s failures {fails}", flush=True)
    print("now LIST the target dirs — 2xx writes do not prove the files landed where you meant")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
