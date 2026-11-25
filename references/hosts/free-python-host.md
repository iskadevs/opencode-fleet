# Free Python host with a REST API

Cheap/free Python deployments for Telegram bots and small services. No shell; a dashboard plus a
Bearer-token API.

## Plan check before you deploy

Typical free tier: ~256 MB RAM, 25 % CPU, 512 MB disk, one deployment, manual renewal every few
days (the server stops otherwise). That fits a micro bot, not an agent framework — a Python agent
with a venv and dependencies needs ~0.5–1 GB, so pick at least a 2 GB tier for it.

## API

Base `https://<provider>/api/v1`, `Authorization: Bearer <key>` (0600 file).

- `GET /account`, `/deployments`, `/deployments/{id}` (startup/state/ports).
- Files: `GET …/files?path=`, `GET …/files/content?path=`, `POST …/files/content {path, content}`
  (creates dirs), `POST …/files/delete {files:[…]}`. `DELETE /files*` 404s.
- Env: `GET …/env` (secret values masked), `POST …/env {key, value}`; system vars read-only.
- Startup: `GET …/startup`, `PATCH …/startup {startCommand}` (the entry-file field is irrelevant
  when the command is explicit).
- Power: `POST …/power {action: start|stop|restart|kill}` — `/restart` etc. do not exist.
- Logs: `GET …/logs` → `{lines, state, settled}`; runtime stdout appears there.

## Python deployment pattern

```bash
cd /home/container && ([ -x .venv/bin/python ] || python3 -m venv .venv) \
  && .venv/bin/pip install --disable-pip-version-check -q . \
  && exec .venv/bin/python -u main.py
```

A `pyproject.toml` in the uploaded ZIP is enough for dependencies. Secrets as env vars, never
files. Without an API key the owner uploads a ZIP and edits the start command in the dashboard —
do not assume dashboard access.

## Telegram-token pitfall

Only one consumer may long-poll a bot token. `getUpdates?timeout=0` returning
**409 Conflict: terminated by other getUpdates request** means another process (often an old
template deployment) still holds it. Check `getWebhookInfo` (empty `url`,
`pending_update_count: 0`) and stop the old consumer before debugging the new deployment.
