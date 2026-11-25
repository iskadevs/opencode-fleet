# Short-lived dev sandbox

A cloud dev box driven by a provider CLI. Useful for agent experiments and CI, not for a
24/7 HTTPS fleet member.

## Typical state

- CLI login via an OAuth provider; one or a few free boxes with several vCPUs, 4–8 GiB RAM and a
  persistent `/data` volume; HOME often `/data/home`.
- Coding agents may be preinstalled but unauthenticated — check env vars and login dirs.

## Limits to plan around

- Free plan: a managed max-run (e.g. 120 minutes) enforced server-side, cooldowns on wake, no UDP
  egress. Activity does not extend the max-run.
- Port publishing exposes HTTPS/TCP-TLS only → no Hysteria2/QUIC/WireGuard.
- Boxes are disposable: state beyond `/data` is lost; snapshots are manual.

Do not build activity/auto-wake workarounds — they violate ToS and get accounts banned. Use the
provider's own CLI skill for commands and current limits instead of re-deriving them.

## When to use it

- Reproducing a build/test failure on a clean Debian image.
- Running an agent that needs a full toolchain and a public HTTPS port for a short window.
- Not for: OpenCode instances that must stay reachable, VPN/proxy nodes, long-running bots.
