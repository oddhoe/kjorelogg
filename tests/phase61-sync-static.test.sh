#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
module="$root/docs/pilot-sync-v105.js"
pilot="$root/docs/pilot-index.html"
expected=11d36e1a0b7d7fbdf6c4ad94d54b9d1f1ac8c532b77b23e753d34452538ab4f7
test "$(sha256sum "$root/docs/index.html" | cut -d' ' -f1)" = "$expected"
test "$(sha256sum "$root/docs/index1.html" | cut -d' ' -f1)" = "$expected"
rg -q "const VERSION='v2.0.105',PREFIX='TEST_PHASE61_'" "$module"
rg -q "assertTestKey\(m.entity_key\)" "$module"
rg -q "phase61Sync\.syncNow\(\)" "$pilot"
rg -q "const APP_VERSION='v2.0.105'" "$pilot"
if rg -q "syncEngine\?\.syncNow\(\)" "$pilot"; then
  echo 'FAIL old push-first sync remains callable in pilot'
  exit 1
fi
python3 - "$module" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
body=s[s.index('async function syncNow()'):s.index('async function release()')]
steps=["versionCheck(client)","preflight(client,dataset)","pull(client,dataset)","acquire(client,user,dataset,before.lease)","push(client,user,dataset,lease)"]
positions=[body.index(x) for x in steps]
assert positions == sorted(positions), positions
print('PASS phase61 ordering: version → preflight → pull → lease → push')
PY
echo 'PASS phase61 prefix, pilot version and production SHA guards'
