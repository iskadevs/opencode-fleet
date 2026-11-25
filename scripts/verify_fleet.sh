#!/usr/bin/env bash
# Health check for an OpenCode fleet published through one edge.
#
# Configure via env:
#   BASE_DOMAIN   e.g. 203-0-113-10.nip.io   (alias is prefixed as <alias>.<BASE_DOMAIN>)
#   SECRETS_DIR   directory holding <alias>-password files (default ~/.secrets)
#   ALIASES       space-separated aliases (default: "a b c d e f")
#   EXPECTED      expected skill count (default 18 = 15 installed + 3 builtins)
#
# Usage: verify_fleet.sh [alias...]
set -u
SECRETS_DIR="${SECRETS_DIR:-$HOME/.secrets}"
BASE_DOMAIN="${BASE_DOMAIN:-}"
EXPECTED="${EXPECTED:-18}"

if [ -z "$BASE_DOMAIN" ]; then
  echo "set BASE_DOMAIN (e.g. 203-0-113-10.nip.io)" >&2
  exit 2
fi

targets=("$@")
if [ ${#targets[@]} -eq 0 ]; then
  # shellcheck disable=SC2206
  targets=(${ALIASES:-a b c d e f})
fi

fail=0
for a in "${targets[@]}"; do
  pf="$SECRETS_DIR/$a-password"
  if [ ! -r "$pf" ]; then
    echo "$a: MISSING $pf"
    fail=1; continue
  fi
  url="https://$a.$BASE_DOMAIN"
  anon=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url/api/config")
  body=$(curl -s -o "/tmp/.vf_$a" -w '%{http_code} %{time_total}' --max-time 30 \
            -u "opencode:$(cat "$pf")" "$url/api/skill")
  code=${body%% *}; t=${body##* }
  count=$(python3 - "$a" <<'PY'
import json, sys
try:
    print(len(json.load(open(f"/tmp/.vf_{sys.argv[1]}"))["data"]))
except Exception:
    print("-")
PY
)
  printf '%-6s anon=%-3s auth=%-3s skills=%-3s t=%ss  %s\n' "$a" "$anon" "$code" "$count" "$t" "$url"
  [ "$code" = "200" ] && [ "$count" = "$EXPECTED" ] || fail=1
done
exit $fail
