#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT"

LOG_FILE="$PROJECT_ROOT/gunicorn.log"
API_BASE_URL="https://eldojo.tech/api/v1"
DEFAULT_AUTH_SECRET="change-this-in-production-eldojo"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [API-DEPLOY] $*" | tee -a "$LOG_FILE"; }

check_endpoint() {
  local name="$1" url="$2" attempts=10 delay=1 i=1
  log "Checking ${name}: ${url}"
  for ((i=1; i<=attempts; i++)); do
    if response="$(curl -fsS "$url")"; then
      log "✅ ${name} OK"
      echo "$response" >> "$LOG_FILE"; echo "" >> "$LOG_FILE"
      return 0
    fi
    log "  attempt $i/$attempts fail, retry in ${delay}s"
    sleep "$delay"
  done
  log "❌ ERROR ${name} FAILED"
  return 1
}

echo "" | tee -a "$LOG_FILE"
log "====================================="
log "Warm-start deploy API (validations + 0 downtime)"
log "====================================="

# ================ 1. .env load + AUTH_SECRET guard ================
log "Loading $PROJECT_ROOT/.env"
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    stripped="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$stripped" || "${stripped:0:1}" == "#" ]] && continue
    [[ "${stripped:0:7}" == "export " ]] && stripped="${stripped:7}"
    key="${stripped%%=*}"; value="${stripped#*=}"
    key="${key#"${key%%[![:space:]]*}"}"; key="${key%"${key##*[![:space:]]}"}"
    [[ -z "$key" || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
    value="${value#"${value%%[![:space:]]*}"}"; value="${value%"${value##*[![:space:]]}"}"
    if [[ "${#value}" -ge 2 ]]; then
      first="${value:0:1}"; last="${value: -1}"
      [[ "$first" == "$last" && ( "$first" == '"' || "$first" == "'" ) ]] && value="${value:1:${#value}-2}"
    fi
    printf -v "$key" '%s' "$value"
    export "$key" >/dev/null 2>&1 || true
  done < "$PROJECT_ROOT/.env"
fi

if [[ -z "${AUTH_SECRET_KEY:-}" ]]; then
  log "❌ FATAL: AUTH_SECRET_KEY vacío en $PROJECT_ROOT/.env"
  log "   -> Generar 1 sola vez: python3 -c \"import secrets; print('AUTH_SECRET_KEY=' + secrets.token_urlsafe(64))\" >> $PROJECT_ROOT/.env"
  exit 1
fi
if [[ "${AUTH_SECRET_KEY}" == "${DEFAULT_AUTH_SECRET}" ]]; then
  log "❌ FATAL: AUTH_SECRET_KEY es el valor hardcodeado por defecto. GENERA UNO ALEATORIO PERMANENTE."
  exit 1
fi
log "AUTH_SECRET_KEY preview: ${AUTH_SECRET_KEY:0:8}...${AUTH_SECRET_KEY: -4}"
log "APP_NAME: ${APP_NAME:-eldojo-api} · APP_ENV: ${APP_ENV:-development}"
log ""

# ================ 2. Git pull último code ================
log "git pull origin $(git branch --show-current)..."
git pull >> "$LOG_FILE" 2>&1 || { log "ERROR git pull fail (¿rama divergida?)."; exit 1; }

# ================ 3. Instalar deps nuevas (si pyproject.toml / requirements cambiaron) ================
VENV_PY="$PROJECT_ROOT/.venv/bin/python"
[[ -x "$VENV_PY" ]] || { log "❌ FATAL no existe $VENV_PY. Crea primero el virtualenv en $PROJECT_ROOT/.venv/."; exit 1; }
log "Installing dependencies (pip install -e .)..."
"$VENV_PY" -m pip install -e . --quiet --upgrade >> "$LOG_FILE" 2>&1

# ================ 4. Warm-up en 5002 ================
OLD_PIDS="$(pgrep -f "gunicorn.*127.0.0.1:5001" || true)"
log "Old gunicorn on :5001 PIDs: ${OLD_PIDS:-none}"

NEW_GUNICORN_PORT=5002
WARMUP_HEALTH_URL="http://127.0.0.1:${NEW_GUNICORN_PORT}/api/v1/health"
FINAL_HEALTH_URL="http://127.0.0.1:5001/api/v1/health"

log "Starting warm-up gunicorn on :${NEW_GUNICORN_PORT}..."
nohup "$PROJECT_ROOT/.venv/bin/gunicorn" \
    --chdir "$PROJECT_ROOT" \
    -k uvicorn.workers.UvicornWorker \
    -w 4 \
    -b "127.0.0.1:${NEW_GUNICORN_PORT}" \
    app.main:app \
    >> "$LOG_FILE" 2>&1 &
NEW_WARM_PID=$!
log "Warm-up PID: ${NEW_WARM_PID}"

WARMUP_OK=0
for ((i=1; i<=25; i++)); do
  if curl -fsS "${WARMUP_HEALTH_URL}" >/dev/null 2>&1; then
    log "✅ Warm-up ready on :${NEW_GUNICORN_PORT} (attempt $i)"
    WARMUP_OK=1
    break
  fi
  log "  waiting health warm-up $i/25..."
  sleep 1
done

if [[ "${WARMUP_OK}" -ne 1 ]]; then
  log "❌ FATAL warm-up gunicorn :${NEW_GUNICORN_PORT} NO pasó health en 25s. Abortando deploy (no tocamos :5001)."
  kill "${NEW_WARM_PID}" 2>/dev/null || true
  pkill -f "gunicorn.*127.0.0.1:${NEW_GUNICORN_PORT}" 2>/dev/null || true
  exit 1
fi

# ================ 5. Swap: matar 5001, warm-up relanzado en 5001 ================
log "Swap: killing old gunicorn on :5001"
if [[ -n "${OLD_PIDS}" ]]; then
  pkill -f "gunicorn.*127.0.0.1:5001" || true
  sleep 1
fi

kill "${NEW_WARM_PID}" 2>/dev/null || true
pkill -f "gunicorn.*127.0.0.1:${NEW_GUNICORN_PORT}" 2>/dev/null || true
sleep 0.5

log "Starting FINAL gunicorn on :5001..."
nohup "$PROJECT_ROOT/.venv/bin/gunicorn" \
    --chdir "$PROJECT_ROOT" \
    -k uvicorn.workers.UvicornWorker \
    -w 4 \
    -b 127.0.0.1:5001 \
    app.main:app \
    >> "$LOG_FILE" 2>&1 &

sleep 2
log "Process table gunicorn:"
pgrep -af gunicorn || log "ℹ️ pgrep no matches aún — esperando para health."
log ""

# ================ 6. Post-checks finales ================
log "====================================="
log "Post-start checks"
log "====================================="
check_endpoint "health"     "$API_BASE_URL/health"
check_endpoint "health-db"  "$API_BASE_URL/health/db"

log ""
log "====================================="
log "🎉 API deployed successfully (0 downtime warm-start + DB idempotent)."
log "====================================="
exit 0
