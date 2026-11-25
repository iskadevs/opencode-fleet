# opencode-fleet

An agent skill (runbook) for running several [OpenCode](https://opencode.ai) servers across
cheap/free container hosts and publishing them through a single edge VPS.

It covers the reusable method, not a specific installation:

- six-step instance recipe (runtime → secret → localhost bind → supervisor → edge publish → verify)
- host-kind references: SSH sandbox, Developer-API container, Pterodactyl panel without a shell,
  free Python host, disposable dev sandbox
- edge front pattern: nginx server blocks with SAN certs, WebSocket upgrade, SSE-safe proxying,
  systemd SSH tunnels
- installing a shared global skill tree on every instance (tar over SSH, panel `files/write`,
  container upload + extract) and verifying it through `GET /api/skill`
- failure signatures that look like bugs but are not (multi-minute cold starts, `httpReady:false`,
  path-nesting uploads, provider alias rate limits)

## Install

This is a standard agent skill: the directory contains `SKILL.md` with YAML frontmatter.

- OpenCode: copy into `~/.config/opencode/skills/opencode-fleet/` (or `.opencode/skills/` in a
  project).
- Claude Code / compatible harnesses: `~/.claude/skills/` or `~/.agents/skills/`.

## Layout

```
SKILL.md
references/from-scratch.md          end-to-end walkthrough
references/edge-front.md            nginx + SSH tunnels on the edge VPS
references/skills-install.md        skill-tree deployment, three transports
references/hosts/*.md               one file per host kind
scripts/verify_fleet.sh             health check: anon/auth codes, skill count, latency
scripts/pterodactyl_upload.py       bulk upload that refuses path-nesting traps
scripts/devapi_client.py            idempotent Developer-API client with 429 backoff
```

## Configuration

No hosts, IPs, credentials or personal data are included. Fill in your own values via the
inventory table in `SKILL.md` and the environment variables the scripts read
(`BASE_DOMAIN`, `SECRETS_DIR`, `DEVAPI_BASE`, `DEVAPI_KEY`).

## License

MIT
