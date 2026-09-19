#!/usr/bin/env bash
# Blue-green production deployment with health-gated traffic switch and rollback.
set -Eeuo pipefail
umask 027

APP_ROOT="${TLF_APP_ROOT:-/opt/tax-lien-finder}"
REPO_DIR="${TLF_REPO_DIR:-$APP_ROOT/repo}"
RELEASES_DIR="$APP_ROOT/releases"
CURRENT_LINK="$APP_ROOT/current"
SHARED_DIR="$APP_ROOT/shared"
RUNTIME_DIR="${TLF_RUNTIME_DIR:-/run/tax-lien-finder}"
UPSTREAM_FILE="${TLF_UPSTREAM_FILE:-/etc/nginx/snippets/tlf-active-upstream.conf}"
PYTHON_BIN="${TLF_PYTHON_BIN:-python3.12}"
HEALTH_RETRIES="${TLF_HEALTH_RETRIES:-30}"
SHA="${TLF_DEPLOY_SHA:-${1:-}}"

if [[ ! "$SHA" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "TLF_DEPLOY_SHA must be a full 40-character commit SHA" >&2
  exit 2
fi
if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "Deployment repository is missing: $REPO_DIR" >&2
  exit 2
fi

if [[ $(id -u) -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo --non-interactive)
fi

for command in git curl tar "$PYTHON_BIN" nginx systemctl; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 2; }
done

git -C "$REPO_DIR" cat-file -e "$SHA^{commit}"
release_id="$(date -u +%Y%m%dT%H%M%SZ)-${SHA:0:12}"
release_dir="$RELEASES_DIR/$release_id"

"${SUDO[@]}" install -d -m 0755 "$RELEASES_DIR" "$SHARED_DIR" "$RUNTIME_DIR"
"${SUDO[@]}" install -d -m 0755 -o "$(id -un)" -g "$(id -gn)" "$release_dir"
git -C "$REPO_DIR" archive "$SHA" | tar -x -C "$release_dir"

if [[ ! -f "$SHARED_DIR/backend.env" ]]; then
  echo "Missing production environment file: $SHARED_DIR/backend.env" >&2
  exit 2
fi
ln -s "$SHARED_DIR/backend.env" "$release_dir/backend/.env"

"$PYTHON_BIN" -m venv "$release_dir/backend/.venv"
"$release_dir/backend/.venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$release_dir/backend/.venv/bin/python" -m pip install --disable-pip-version-check -r "$release_dir/backend/requirements.txt"
PYTHONPATH="$release_dir/backend/src" "$release_dir/backend/.venv/bin/python" -m compileall -q "$release_dir/backend/src"

active_port=""
if [[ -f "$UPSTREAM_FILE" ]]; then
  active_port="$(sed -nE 's/.*127\.0\.0\.1:([0-9]+).*/\1/p' "$UPSTREAM_FILE" | head -1)"
fi
if [[ "$active_port" == "8001" ]]; then
  old_slot="blue"; new_slot="green"; new_port="8002"
else
  old_slot="green"; new_slot="blue"; new_port="8001"
fi

runtime_file="$RUNTIME_DIR/$new_slot.env"
runtime_tmp="$(mktemp)"
printf 'RELEASE_DIR=%s\nPORT=%s\nGUNICORN_BIND=127.0.0.1:%s\n' "$release_dir" "$new_port" "$new_port" > "$runtime_tmp"
"${SUDO[@]}" install -m 0640 "$runtime_tmp" "$runtime_file"
rm -f "$runtime_tmp"

"${SUDO[@]}" systemctl stop "tax-lien-api@$new_slot.service" 2>/dev/null || true
"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl start "tax-lien-api@$new_slot.service"

healthy=false
for ((attempt=1; attempt<=HEALTH_RETRIES; attempt++)); do
  if curl --fail --silent --max-time 3 "http://127.0.0.1:$new_port/health" >/dev/null; then
    healthy=true
    break
  fi
  sleep 1
done
if [[ "$healthy" != true ]]; then
  "${SUDO[@]}" journalctl -u "tax-lien-api@$new_slot.service" -n 100 --no-pager || true
  "${SUDO[@]}" systemctl stop "tax-lien-api@$new_slot.service" || true
  echo "New release failed its private health check; live traffic was not changed" >&2
  exit 1
fi

previous_release="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
link_tmp="$APP_ROOT/.current-$release_id"
"${SUDO[@]}" ln -s "$release_dir" "$link_tmp"
"${SUDO[@]}" mv -Tf "$link_tmp" "$CURRENT_LINK"

upstream_tmp="$(mktemp)"
printf 'server 127.0.0.1:%s;\n' "$new_port" > "$upstream_tmp"
"${SUDO[@]}" install -m 0644 "$upstream_tmp" "$UPSTREAM_FILE.new"
rm -f "$upstream_tmp"

rollback() {
  echo "Post-switch health check failed; restoring the previous release" >&2
  if [[ -n "$previous_release" && -d "$previous_release" ]]; then
    rollback_link="$APP_ROOT/.rollback-$release_id"
    "${SUDO[@]}" ln -s "$previous_release" "$rollback_link"
    "${SUDO[@]}" mv -Tf "$rollback_link" "$CURRENT_LINK"
  fi
  if [[ -n "$active_port" ]]; then
    printf 'server 127.0.0.1:%s;\n' "$active_port" | "${SUDO[@]}" tee "$UPSTREAM_FILE.new" >/dev/null
    "${SUDO[@]}" mv -f "$UPSTREAM_FILE.new" "$UPSTREAM_FILE"
    "${SUDO[@]}" nginx -t && "${SUDO[@]}" systemctl reload nginx
  fi
  "${SUDO[@]}" systemctl stop "tax-lien-api@$new_slot.service" || true
}

"${SUDO[@]}" mv -f "$UPSTREAM_FILE.new" "$UPSTREAM_FILE"
if ! "${SUDO[@]}" nginx -t; then
  rollback
  exit 1
fi
"${SUDO[@]}" systemctl reload nginx

if ! curl --fail --silent --max-time 5 http://127.0.0.1/health >/dev/null; then
  rollback
  exit 1
fi

if [[ -n "$active_port" ]]; then
  "${SUDO[@]}" systemctl stop "tax-lien-api@$old_slot.service" || true
fi

echo "Deployment successful: $release_id on $new_slot ($new_port)"
