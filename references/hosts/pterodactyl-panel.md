# Pterodactyl panel host, no shell

A game-panel container where the only entry point is a startup file (typically `index.js`). No
SSH, no `exec`; everything goes through the client API.

## API

- Base `https://<panel>/api/client`, server id `<uuid>`; key `ptlc_…` in a 0600 file, **line 1
  only** (concatenating header lines yields an invalid token).
- **Send a curl-like User-Agent.** Python-urllib's default is blocked by Cloudflare WAF with 403
  `error code: 1010`.
- `/resources`, `/files/list?directory=`, `/files/contents?file=`,
  `POST /files/write?file=` (creates dirs), `POST /files/delete {root, files:[…]}`,
  `POST /files/rename`, `POST /power {signal: start|restart|stop|kill}`.
- `/startup` is usually read-only via the client API (405) — design around the existing variables.
- `/files/list` may 500 (`DaemonConnectionException`) on large/root-owned dirs; retry or narrow the
  path. `/files/delete` is POST, not DELETE (DELETE returns 405).

## Multiplexer pattern

The startup file is a Host-routing multiplexer on `0.0.0.0:<mux>` that spawns and supervises the
children:

- routes `<child>.<domain>` → `127.0.0.1:<p_child>`;
- unknown Host → 421; plain HTTP → 308 to HTTPS; requires `X-Forwarded-Proto: https`;
- child env sets `HOME`, `OPENCODE_SERVER_PASSWORD`, and for Bun also
  `OPENCODE_DISABLE_FILEWATCHER=true` (Bun otherwise blocks its event loop watching `/`);
- logs: one mux log (`multi.log`) plus per-child logs.

Editing rules: read the file → write `index.js.bak-<UTC>` → patch narrowly → `power restart`.
A wrong edit here crash-loops everything; keep the backup one API call away.

## Cold start is slow

Expect **5–8 minutes** after restart before ports listen: large binaries read cold from slow disk,
and each instance spends ~150 s in `location services booted` while metadata fetches time out at
10 s. During that window the mux logs `connect ECONNREFUSED` and `/resources` reports
`memory_bytes:0` with `current_state: running`. That is a slow boot, **not** a crash loop — wait
and probe. Check the child's own log before concluding anything.

## File uploads — the path trap

`?file=` / `?directory=` are **relative to the server root** (`/` == the egg's working directory,
commonly `/home/container`). Passing an absolute `/home/container/...` silently creates
`/home/container/home/container/...`: every write returns 2xx and OpenCode never sees the files.
Always list the intended directory after uploading. Use `scripts/pterodactyl_upload.py`, which
refuses absolute data paths.

Cleanup of a mistaken tree:
`POST /files/delete {"root":"/home/container","files":[".config",".opencode"]}`.

## Public exposure

Edge relay: `ssh -N -L 127.0.0.1:<local>:<node-ip>:<mux> -i /root/.ssh/tunnel_key -p <ssh-port>
root@<sandbox>` as a systemd service, because direct edge→panel HTTPS can degrade to seconds per
request. nginx uses the relay as primary upstream and the panel hostname as backup.

## Skills

Write into the config dir each instance reports (`GET /api/config`) — for the Node child that is
usually the panel-visible path; for the Bun child it is inside its custom `HOME`. Node picks skills
up live; Bun needs a power restart. Verify `GET /api/skill` on each alias.
