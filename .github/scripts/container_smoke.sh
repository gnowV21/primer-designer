#!/usr/bin/env bash
# Smoke test of a running Dockerfile.vercel container (deploy/vercel).
#   .github/scripts/container_smoke.sh http://127.0.0.1:8080
# Health, one design, the SPA fallback, JSON 404 for unknown /api, and no internal
# file served under any spelling of its path.
set -euo pipefail
BASE="${1:-http://127.0.0.1:8080}"
fail=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ok()   { echo "ok    $*"; }
bad()  { echo "FAIL  $*"; fail=1; }

# health
curl -fsS "$BASE/api/health" | grep -q '"status":"ok"' && ok "/api/health" || bad "/api/health"

# one design (backend defaults; BLAST must be available in the image)
curl -fsS -m 280 -H 'Content-Type: application/json' -o "$tmp/design.json" \
  -d '{"sequence":{"mirnaId":"hsa-miR-21-5p","matureSequence":"UAGCUUAUCAGACUGAUGUUGA"}}' \
  "$BASE/api/design"
python3 - "$tmp/design.json" <<'PY' && ok "/api/design hsa-miR-21-5p" || bad "/api/design hsa-miR-21-5p"
import json, sys
d = json.load(open(sys.argv[1]))
rs = d["ranking_summary"]
assert len(d["top3"]) == 3, d.get("top3")
assert rs["system"] == "tiered" and rs["blast_available"] is True, rs
assert d["stemloop_rt"]["sequence"] == "GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTCAACA"
print("   top1", d["top3"][0]["sequence"], d["top3"][0]["grade"])
PY

# miRBase lookup from the local 22.1 database
curl -fsS "$BASE/api/mirbase/hsa-miR-21-5p" | python3 -c '
import json,sys; d=json.load(sys.stdin)
assert d["source"]=="local" and d["mirbase_release"]=="22.1", d' \
  && ok "/api/mirbase local 22.1" || bad "/api/mirbase local 22.1"

# BLAST DB on the pinned release
curl -fsS "$BASE/api/blast-status" | python3 -c '
import json,sys; d=json.load(sys.stdin)
assert d["available"] is True and d["sequences_count"]==48885, d' \
  && ok "/api/blast-status" || bad "/api/blast-status"

# SPA fallback
curl -fsS -o "$tmp/index.html" "$BASE/"
grep -q '<div id="root">' "$tmp/index.html" && ok "/ is index.html" || bad "/ is index.html"
for p in /design /results /history /design/advanced; do
  curl -fsS -o "$tmp/page" "$BASE$p"
  cmp -s "$tmp/page" "$tmp/index.html" && ok "$p -> index.html" || bad "$p -> index.html"
done

# unknown /api -> JSON 404
code=$(curl -s -o "$tmp/api404" -w '%{http_code}' "$BASE/api/khong-ton-tai")
[ "$code" = 404 ] && python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$tmp/api404" \
  && ok "/api/khong-ton-tai JSON 404" || bad "/api/khong-ton-tai ($code)"

# internal files never served (index.html or 404 only)
for p in /SPEC_algorithm.md /backend/app.py /HANDOFF_THESIS_STATUS.md /.git/config \
         /../backend/app.py /%2e%2e/backend/app.py /..%2fbackend%2fapp.py \
         /app.py /static/openapi.yaml /backend/requirements.txt /CLAUDE.md \
         /backend/db/mirbase.db /assets/../../backend/app.py /benchmark/benchmark_results.json; do
  code=$(curl -s --path-as-is -o "$tmp/leak" -w '%{http_code}' "$BASE$p")
  if [ "$code" = 404 ] || { [ "$code" = 200 ] && cmp -s "$tmp/leak" "$tmp/index.html"; }; then
    ok "$p ($code, no file content)"
  elif [ "$code" = 400 ]; then
    ok "$p (400 from the server, no file content)"
  else
    bad "$p returned $code with other content"; head -c 200 "$tmp/leak"; echo
  fi
  if grep -q -e 'from flask import' -e 'import logging' -e '\[core\]' -e 'SQLite format' "$tmp/leak"; then
    bad "$p leaked file content"
  fi
done

exit $fail
