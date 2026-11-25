# Container host with a Developer API

Containers created and driven over REST; no SSH.

## API shape

Base `https://<provider>/api/v1/developer`, `Authorization: Bearer <key>`; key in a 0600 file,
never argv/chat.

- **Writes require `Idempotency-Key`** (16–64 chars, e.g. `uuid4().hex`) — otherwise 422.
- Rate limits (per key) return 429 with `Retry-After`; 503/409 also occur. Honor `Retry-After`.
- Workload creation returns 202 + async operation; poll `queueState` / `operation.phase`. A
  top-level `status` field is often absent and can lag behind reality.
- Env: one variable per `PUT /workloads/{id}/env` with `{key, value, isSecret}` — not an array.
- Files: `PUT /workloads/{id}/file {path, type:"file", content, createOnly:false}`; read back
  `GET …/file?path=`. Bulk: `POST …/files/upload` (base64, ≤5.3 MB) →
  `POST …/files/extract/preview` (→ revision) → `POST …/files/extract`
  (`path`, `destination`, `revision`, `overwrite`). `POST …/files/batch` moves/deletes/copies.
- `console/command` is not a real shell.
- HOME is often `/`; config dir `/.config/opencode`.
- Raw ports are HTTP only (TLS fails); provider aliases often rate-limit heavily — use your own
  edge front for anything interactive.

## Deploying OpenCode

Node workload start command (idempotent):

```bash
[ -x node_modules/.bin/opencode ] || npm i --no-save @opencode/cli@<version>
exec node_modules/.bin/opencode serve --hostname 127.0.0.1 --port $PORT
```

Bun workload: Bun runs `bun install` before every start and blocks dependency postinstalls
("Blocked N postinstalls"). Packages added with `npm --no-save` can disappear on restart — the
start script must re-check and re-add them idempotently.

Set `OPENCODE_SERVER_PASSWORD` as a secret env var equal to the local password file. Bind a
concrete local IP, never `0.0.0.0`.

## Common failure modes

| Code | Cause |
|---|---|
| 422 "Supply an Idempotency-Key" | header missing on a write |
| 429 "operations are busy" | rate limit — sleep `Retry-After` |
| 409 "archive or destination changed" | extract over an existing/renamed dir — use a fresh destination |
| alias 429 storm on UI | provider proxy rate limit — switch to your edge URL |
| `httpReady:false` but curl 200 | flag is cosmetic; trust the HTTP probe |

## Skills

Upload a tgz, extract to a path that yields `<config>/skills/…`, then verify with
`GET /api/skill`. When extracting over an existing dir fails with 409, extract to a fresh
destination and move with `files/batch`. See `skills-install.md`.
