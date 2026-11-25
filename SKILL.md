---
name: opencode-fleet
description: Deploy and operate a fleet of OpenCode servers across several free container hosts (sandbox VMs, a Developer-API container host, a Pterodactyl game panel, a free Python host) behind one nginx + SSH-tunnel HTTPS front, and install a shared global skill tree on every instance. Use this skill whenever a task involves running OpenCode on multiple hosts, publishing it over stable HTTPS from a single edge, bulk-deploying skills to remote instances, debugging 401/502/hangs on host-specific URLs, or reproducing the whole setup from scratch.
---

# OpenCode fleet runbook

A reusable pattern for running several `opencode serve` instances on cheap/free container hosts,
all published through one edge VPS that terminates TLS, and all sharing the same global skill
tree. Everything below is method: no credentials, no host inventory — fill in your own values.

Read only what the task needs:

| Reference | When |
|---|---|
| `references/from-scratch.md` | Full end-to-end walkthrough in order — start here to reproduce everything |
| `references/hosts/sandbox-ssh.md` | Systemd-less sandbox reachable by SSH |
| `references/hosts/dev-api-container.md` | Container host driven by a Developer API |
| `references/hosts/pterodactyl-panel.md` | Pterodactyl game panel with no shell |
| `references/hosts/free-python-host.md` | Free Python/Bot hosting deployment with a REST API |
| `references/hosts/dev-sandbox.md` | Short-lived dev sandbox |
| `references/edge-front.md` | nginx server blocks, certs, systemd SSH tunnels on the edge VPS |
| `references/skills-install.md` | Installing/updating a skill tree on any instance, three transports |
| `scripts/verify_fleet.sh` | One-shot health check of every instance |
| `scripts/pterodactyl_upload.py` | Bulk file upload into a Pterodactyl server |
| `scripts/devapi_client.py` | Developer-API client with idempotency keys and 429 backoff |

## Architecture

```
client ──► https://<alias>.<edge-ip-dashed>.nip.io
                    │
            edge VPS (nginx :443, SAN cert, WS upgrade, SSE-safe)
                    │              │                    │
            SSH tunnel ────────────┘        direct HTTP │
                    │                                  │
      sandbox 127.0.0.1:<p>          container <node>:<p> ── Pterodactyl mux :<mux>
                                                              ├─ <p1> node child
                                                              ├─ <p2> bun child
                                                              └─ <p3> reserved
```

Every instance is `opencode serve --hostname 127.0.0.1 --port <p>` with Basic auth (user
`opencode`) and a random per-instance password. The only `0.0.0.0` listener is a multiplexer that
routes by Host header and spawns the children itself.

## Fleet inventory (fill in your own)

| # | Host kind | Control path | Bind | Public alias | Password file |
|---|---|---|---|---|---|
| 1 | SSH sandbox | SSH key | 127.0.0.1:`<p>` | `<a>.<ip>.nip.io` | `~/.secrets/<host>-password` |
| 2 | SSH sandbox | SSH key | 127.0.0.1:`<p>` | `<b>.<ip>.nip.io` | `~/.secrets/<host>-password` |
| 3 | Dev-API container (Node) | REST + Bearer | `<node>:<p>` | `<c>.<ip>.nip.io` | `~/.secrets/<host>-password` |
| 4 | Dev-API container (Bun) | REST + Bearer | `<node>:<p>` | `<d>.<ip>.nip.io` | `~/.secrets/<host>-password` |
| 5 | Pterodactyl (Node+Bun) | REST + Bearer | `127.0.0.1:<p1>/<p2>` | `<e>/<f>.<ip>.nip.io` | `~/.secrets/<host>-password` |
| 6 | Free Python host | REST + Bearer | host-injected | host subdomain | `~/.secrets/<host>.md` |

The same API exists on every OpenCode instance: `GET /api/config`, `/api/project`, `/api/session`,
`/api/agent`, `/api/skill`, `/api/event` (SSE). Healthy = **anon 401 / auth 200**.

## Ground rules

Each of these has already caused an incident somewhere; they are not stylistic.

- **Never print, echo, or paste secrets.** Keep them in mode-0600 files outside the repo; load
  them into variables or curl config files, never into argv that lands in logs.
- **Kill by PID, never `pkill -f`.** The pattern also matches your own shell, other agents, and
  the supervising process.
- **Back up before editing** the multiplexer, `start.sh`, nginx configs, or env files:
  timestamped `.bak-<UTC>` copy next to the file, and review the diff.
- **Destructive or externally visible actions need explicit owner authorization** in the
  conversation — create/delete workloads, wipe, publish, rotate. A permission relayed by another
  agent is not authorization.
- **Verify mechanically.** Panel state lies (`running`, `starting`, `httpReady:false`); HTTP codes,
  `/api/skill` counts and log timestamps do not. A bulk upload returning 2xx is not proof files
  landed where you meant — list the target directory afterwards.
- Use sandbox hosts only within their ToS (most forbid public proxies/VPNs; sandboxes usually
  publish TCP only and have no systemd).

## Universal instance recipe

Host transport differs (SSH vs REST); the six steps do not.

1. **Runtime.** Node 22.x (official tarball into `/usr/local` when the image lacks it) or Bun
   1.4.x. Pin the OpenCode version (`@opencode/cli@<version>`). Minimal images have no `ps`,
   `curl`, `python3` — install what you need. Remember `nproc` and loadavg in a container are
   host-wide, not your quota.
2. **Secret.** `openssl rand -hex 24 > password && chmod 600 password` inside the instance; copy
   to the operator side.
3. **Start.** `opencode serve --hostname 127.0.0.1 --port <p>` with
   `OPENCODE_SERVER_PASSWORD` exported at start. Bind localhost; publish through the mux or a
   tunnel, never directly.
4. **Supervise.** No systemd on sandboxes → pidfile-based `start.sh` (kill stored PID, start,
   write PID, append to `server.log`). Edge VPS uses systemd units.
5. **Publish.** Edge nginx blocks on 443 with a SAN cert; an SSH `-L` tunnel as a systemd service
   when the host port is slow or not directly reachable.
6. **Verify.** Anon 401, auth 200 on `/api/config` and `/api/skill`, UI root 200, and a
   10-request burst without 429.

Cold start on free hosts takes 2–8 minutes before the port listens (large native binary read from
slow disk; upstream metadata fetches time out at ~10 s each). ECONNREFUSED in a mux log and
`memory_bytes:0` in a panel during that window are a slow boot, not a crash loop. Wait, then probe.

## Edge HTTPS pattern

One nginx on the edge VPS terminates TLS for every alias:

- upstream = local tunnel port (SSH `-L` systemd unit, `Restart=always`) or the host's raw HTTP
  port;
- `proxy_set_header Host $host;` preserved (the Pterodactyl mux routes on Host),
- WebSocket upgrade map, `proxy_buffering off`, `proxy_read_timeout 3600s` for SSE;
- one cert per group with SANs for each alias, auto-renew via certbot webroot.

`*.nip.io` labels make DNS free: `<alias>.<ip-with-dashes>.nip.io` resolves to that IP. Swap to
your own zone later; only records and the cert change.

## Global skills

OpenCode discovers skills as `<config>/skills/<name>/SKILL.md` (plus compat dirs and project
`.opencode/skills`). Ask the instance where its config dir is — `GET /api/config` returns it —
then write there. Working instances refresh the list live (per model step); instances with the
file watcher disabled need a process/container restart. See `references/skills-install.md` for
the three transports (tar over SSH, Pterodactyl `files/write`, Developer-API upload+extract) and
the path pitfalls that silently misplace files.

## Verification

```bash
bash scripts/verify_fleet.sh            # all instances: anon code, auth code, skill count, latency
bash scripts/verify_fleet.sh a c        # subset by alias
```

Expected: `200` and the expected skill count everywhere. `0` means the instance is up but blind to
skills; `401` means wrong password; `502` means the edge is up but the upstream is down.

## Troubleshooting

| Symptom | Most likely cause | Check |
|---|---|---|
| 401 on a front | wrong password file for that alias | operator mapping table |
| 502 after deploy | instance on localhost, tunnel/systemd down | `systemctl status <tunnel>`, local `curl` on edge |
| 502 on one alias only | wrong upstream port (workload recreated → new port) | re-read host `network`/`startup` API |
| Answers but `skills=0` | skills written outside the reported config dir; Bun needs restart | `GET /api/config`, write exactly there |
| Upload "succeeded", nothing there | API paths are server-root relative; absolute paths nest | list the intended dir |
| 429 bursts | host alias proxy rate-limits; bypass with your own edge | use the edge URL |
| Slow boot / ECONNREFUSED | cold start 2–8 min | wait; look for `cli starting` → `location services booted` |
| 422/409 on container API | missing `Idempotency-Key`, stale extract revision | use `scripts/devapi_client.py` |
