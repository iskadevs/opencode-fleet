# Reproducing the fleet from scratch

Ordered walkthrough. References give exact commands per host kind. Placeholders: `<edge-ip>`,
`<alias>`, `<p>` = port, `<node>` = container host node name.

## Phase 0 — prerequisites

- Workstation: `curl`, `python3`, `node`, an SSH key for sandboxes and the edge VPS; on the edge a
  dedicated tunnel key at `/root/.ssh/tunnel_key`.
- A secrets directory outside the repo, mode 700; one 0600 file per credential.
- An edge VPS with a public IP; `*.nip.io` for zero-setup DNS, or your own wildcard-capable zone.
- Owner authorization for anything that creates, deletes, restarts, or publishes.

## Phase 1 — edge front first

Build the front before instances so each deploy is verifiable immediately. See
`edge-front.md`:

1. nginx; `map $http_upgrade $connection_upgrade { … }` in a separate conf.
2. certbot webroot `/var/www/acme`.
3. one server block per host group; upstream = tunnel port or host:port; `Host` preserved,
   `proxy_buffering off`, 3600 s read timeout.
4. systemd SSH tunnels (`Restart=always`) for slow/unreachable host ports.
5. `nginx -t && systemctl reload nginx`; back up `/etc/nginx` first.

## Phase 2 — SSH sandboxes

Detail in `hosts/sandbox-ssh.md`:

```bash
ssh -i <key> -p <ssh-port> root@<sandbox-host>
mkdir -p /srv/opencode && cd /srv/opencode
npm i @opencode/cli@<version>          # Node from tarball into /usr/local if missing
openssl rand -hex 24 > password && chmod 600 password
# start.sh: kill stored PID, start with OPENCODE_SERVER_PASSWORD, write PID, log
bash start.sh
```

Copy the password to the operator side, add an edge tunnel, verify 401/200.

Constraints: no systemd and no boot hook (re-run `start.sh` after pause/restart), TCP-only
published ports, a fraction of a core and ~2 GiB RAM per sandbox.

## Phase 3 — Developer-API containers

Detail in `hosts/dev-api-container.md`:

1. Create workload; poll the async operation until ready; read `network` (raw port) and `env`.
2. Install the CLI in the start command; keep it idempotent (Bun re-runs `bun install` on every
   boot and may drop `npm --no-save` packages).
3. Set the password as a secret env var; start command binds `127.0.0.1` and `$PORT`.
4. Add edge nginx blocks for the two aliases. Raw ports are HTTP-only; host aliases often
   rate-limit — always use your edge.

## Phase 4 — Pterodactyl panel host

No shell; the only entry is a process-manager file started by the egg, which acts as a
Host-routing multiplexer and spawns the OpenCode children. Detail in `hosts/pterodactyl-panel.md`:

1. Read the key; **use a curl User-Agent** (many WAFs 403 python-urllib with `error code: 1010`).
2. The mux listens on `0.0.0.0:<mux>` and routes `<child>.<domain>` → local ports; it usually
   requires `X-Forwarded-Proto: https`, else 421/308.
3. Change things by read → timestamped backup → write → `power restart`.
4. Cold start 5–8 min; do not power-cycle casually.
5. Edge: an SSH relay to the node IP (hostname resolution costs ~0.8 s per channel) plus nginx
   with a backup upstream.

## Phase 5 — free Python host

Detail in `hosts/free-python-host.md`: a deployment driven by `POST /files/content`,
`PATCH /startup`, `POST /env`, `POST /power`, `GET /logs`. Start command creates a venv and runs
the entrypoint; secrets as env vars. Watch plan limits and manual-renewal schedules.

## Phase 6 — dev sandbox (optional)

Detail in `hosts/dev-sandbox.md`. Not part of the HTTPS fleet: short max-run, TCP/TLS-only
publishing, resets. Use for agent experiments, not 24/7 hosting.

## Phase 7 — install the shared skill tree

Follow `skills-install.md`. Three transports:

| Host kind | Transport |
|---|---|
| SSH sandbox | `tar -czf - skills \| ssh … 'tar -xzf - -C <config>'` |
| Pterodactyl | `scripts/pterodactyl_upload.py` (root-relative paths) |
| Dev-API container | upload tgz (base64) → `files/extract/preview` → `files/extract` |

Verify with `scripts/verify_fleet.sh`.

## Phase 8 — verification and handover

1. Every instance `200` + expected skill count.
2. Burst test each front (10 parallel): no 429/502; check `curl -w '%{time_total}'`.
3. Secrets are 0600, absent from any repo, never printed in logs.
4. Record current ports, workload ids and plan expiries in operator notes — they drift when a
   workload is recreated.

## Known decay points

- Container URLs/ports change if a workload is recreated → re-read `network`, update nginx.
- Sandboxes pause when idle with no boot hook → re-run `start.sh` after resume.
- Quick tunnels rotate on restart; a stable nip.io/nginx front is the real entry point.
- Panel hosts: cold starts of minutes, `/startup` read-only via API.
- Free tiers use manual renewal; the server stops if not renewed.
- Paid container plans expire — put the date in the notes.
