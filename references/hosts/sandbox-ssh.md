# Sandbox reachable by SSH

A container VM with root SSH, no systemd, no boot hook, minimal toolkit.

## Access

- `ssh -i <key> -p <port> root@<sandbox-host>`; the control-plane CLI may need its own token and
  can be down while SSH still works.
- Only some keys are accepted; the provider's key listing does not prove a sandbox accepts a key —
  test it.

## Constraints that shape the recipe

- No systemd and no boot hook → supervise with a pidfile `start.sh`, re-run after restart/pause.
- Published ports are TCP/TLS only and map 1:1 (`N` → `N`). No UDP → no Hysteria2/QUIC/WireGuard.
- Per-cgroup quota (e.g. 0.6 CPU, ~2.3 GiB RAM). `nproc`/loadavg are host-wide.
- Minimal image: no `ps`, `curl`, `python3`; install what you need.
- Provider ToS commonly forbids public proxies/VPNs; host web apps/agents only.

## Deploy OpenCode

```bash
# Node 22 if missing
curl -fsSL https://nodejs.org/dist/v22.23.5/node-v22.23.5-linux-x64.tar.xz \
  | tar -xJ -C /usr/local --strip-components=1
mkdir -p /srv/opencode && cd /srv/opencode
npm i @opencode/cli@<version>
openssl rand -hex 24 > password && chmod 600 password
cat > start.sh <<'EOF'
#!/bin/bash
cd /srv/opencode
[ -f server.pid ] && kill "$(cat server.pid)" 2>/dev/null
OPENCODE_SERVER_PASSWORD="$(cat password)" \
  nohup ./node_modules/.bin/opencode serve --hostname 127.0.0.1 --port <p> \
  >> server.log 2>&1 &
echo $! > server.pid
EOF
chmod +x start.sh && ./start.sh
```

`npm i` for the CLI is ~1 GB — check disk before installing on a small sandbox.

## Supervision and recovery

- `start.sh` kills only the recorded PID (never `pkill -f`).
- Verify locally: `curl -su opencode:"$(cat password)" http://127.0.0.1:<p>/api/config` → 200.
- Sandbox pause/restart stops the process; there is no boot hook, so re-run `start.sh`.

## Public exposure

Use your own edge front (`edge-front.md`) — provider quick tunnels rotate names on restart and
some names are account-level (a second tunnel can hijack the route). Keep the stable HTTPS URL as
the primary and tunnels only as debugging fallbacks.

## Skills

Install into `<config>/skills/` over SSH with tar; no restart needed when the file watcher is
enabled. See `skills-install.md`.
