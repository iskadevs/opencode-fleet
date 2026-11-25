# Installing a shared skill tree on every instance

OpenCode discovers skills as directories containing `SKILL.md`:

1. global config dir `<config>/skills/<name>/SKILL.md` (from `GET /api/config`),
2. compat dirs `~/.claude/skills`, `~/.agents/skills`,
3. project `<cwd>/.opencode/skills`.

Depth ≤ 6; hidden dirs and `node_modules` are skipped. Ask the instance where its config dir is
instead of guessing:

```bash
curl -su "opencode:$PW" https://<alias>/api/config
# [{"type":"directory","path":"/root/.config/opencode"}]
```

## Building the tree

Skills are plain directories. Any collection (e.g. a 15-skill engineering set) can be staged
locally and shipped as one archive whose top level is `skills/`:

```bash
tar -czf /tmp/skills.tgz -C /path/to/stage skills
sha256sum /tmp/skills.tgz
```

Count the expected total: builtins the instance ships with + installed skills. Record it, so
verification is a number, not a vibe.

## Transport A — SSH sandbox (tar)

```bash
tar -czf - -C /path/to/stage skills \
  | ssh -i <key> -p <ssh-port> root@<host> 'mkdir -p <config> && tar -xzf - -C <config>'
```

No restart when the file watcher is enabled: the list refreshes per model step (writing skills
into a running instance makes them visible immediately).

## Transport B — Pterodactyl (files/write)

Use `scripts/pterodactyl_upload.py` with **server-root-relative** roots, then verify by listing:

```bash
python3 scripts/pterodactyl_upload.py --src /path/to/stage --roots <config-relative>/skills …
```

The trap: absolute `/home/container/...` paths create a nested `home/container/...` tree, return
2xx, and are never read. A "0 failures" upload proves nothing — list the target directory.

## Transport C — Developer API (upload + extract)

1. `POST …/files/upload` base64 of the tgz (≤5.3 MB) → `/skills.tgz`.
2. `POST …/files/extract/preview {path, destination}` → `revision`.
3. `POST …/files/extract {path, destination, revision, overwrite:false}`.

Rules learned the hard way:

- destination must yield `<config>/skills/…` (archive top level is `skills/`, so destination is
  `<config>`);
- extracting over an existing directory returns 409 "archive or destination changed" — use a
  fresh destination and move with `files/batch`;
- helpers: `scripts/devapi_client.py` (Idempotency-Key + Retry-After).

## Verifying one instance

```bash
PW=$(cat ~/.secrets/<host>-password)
curl -s -u "opencode:$PW" https://<alias>/api/skill \
  | python3 -c 'import sys,json; d=json.load(sys.stdin)["data"]; print(len(d)); print([x["name"] for x in d])'
```

`200` + expected count + expected names = done. Count equals builtins only → files are not where
the instance looks. `401` → wrong password. `502` → front/upstream, not skills.

## Updating later

Overwrite files in place (same directory names) and re-probe. Instances with the file watcher
disabled need a restart (container restart on a panel host: expect the usual slow cold boot).
There is no registry or manifest — discovery is filesystem-based at each model step.
