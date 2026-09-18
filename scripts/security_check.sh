#!/usr/bin/env bash
# Quick security / health smoke tests against a running API.
# Usage: ./scripts/security_check.sh [API_BASE]
set -euo pipefail

API="${1:-http://127.0.0.1:8000}"

echo "== Health =="
curl -sf "$API/health" | head -c 500
echo
echo

echo "== Security headers on /health =="
headers=$(curl -sI "$API/health")
echo "$headers"
echo
for h in "X-Content-Type-Options" "X-Frame-Options" "Referrer-Policy" "Permissions-Policy" "Content-Security-Policy"; do
  if echo "$headers" | grep -qi "^$h:"; then
    echo "OK  $h"
  else
    echo "MISSING  $h"
  fi
done

echo
echo "== Rate limit smoke (signup should eventually 429 if hammered) =="
echo "(skipping hammer in default run — use manually if needed)"

echo
echo "== OpenAPI docs reachable =="
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/docs")
echo "GET /docs → $code"

echo
echo "Done."
