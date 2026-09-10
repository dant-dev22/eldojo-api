#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

MIGRATIONS_DIR="$PROJECT_ROOT/migrations/sql"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [MIGRATE] $*"; }

log "Working dir: $PROJECT_ROOT"
log "Migrations folder: $MIGRATIONS_DIR"

# ================ .env load compatible con python-dotenv ================
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  log "Loading $PROJECT_ROOT/.env"
  while IFS= read -r line || [[ -n "$line" ]]; do
    stripped="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$stripped" || "${stripped:0:1}" == "#" ]] && continue
    [[ "${stripped:0:7}" == "export " ]] && stripped="${stripped:7}"
    key="${stripped%%=*}"
    value="${stripped#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ -z "$key" || ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && continue
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "${#value}" -ge 2 ]]; then
      first="${value:0:1}"
      last="${value: -1}"
      [[ "$first" == "$last" && ( "$first" == '"' || "$first" == "'" ) ]] && value="${value:1:${#value}-2}"
    fi
    printf -v "$key" '%s' "$value"
    export "$key" >/dev/null 2>&1 || true
  done < "$PROJECT_ROOT/.env"
fi

# ================ Resolver credenciales (nombres modernos + legacy) ================
PGHOST="${DATABASE_HOST:-${POSTGRES_HOST:-localhost}}"
PGPORT="${DATABASE_PORT:-${POSTGRES_PORT:-5432}}"
PGUSER="${DATABASE_USER:-${POSTGRES_USER:-eldojo}}"
PGDATABASE="${DATABASE_NAME:-${POSTGRES_DB:-${POSTGRES_DATABASE:-eldojo}}}"
PGPASSWORD="${DATABASE_PASSWORD:-${POSTGRES_PASSWORD:-}}"

export PGHOST PGPORT PGUSER PGDATABASE PGPASSWORD

log "Using DB host=$PGHOST port=$PGPORT user=$PGUSER db=$PGDATABASE"
log "Checking psql client..."
command -v psql >/dev/null 2>&1 || {
  log "FATAL: psql client not installed. Run: apt-get install -y postgresql-client"
  exit 1
}

# ================ Ejecutar todas las migraciones SQL ordenadas ================
TOTAL=0
APPLIED=0
SKIPPED=0
if [[ -d "$MIGRATIONS_DIR" ]]; then
  shopt -s nullglob
  mapfile -t SQL_FILES < <(find "$MIGRATIONS_DIR" -maxdepth 1 -type f -name '*.sql' | sort)
  shopt -u nullglob

  TOTAL=${#SQL_FILES[@]}
  log "Found $TOTAL migration SQL files in $MIGRATIONS_DIR"

  for sql_file in "${SQL_FILES[@]}"; do
    base="$(basename "$sql_file")"
    log "▶ Applying: $base"
    set +e
    OUTPUT=$(psql -v ON_ERROR_STOP=1 -f "$sql_file" 2>&1)
    RC=$?
    set -e
    if [[ $RC -eq 0 ]]; then
      log "  ✅ OK $base"
      APPLIED=$((APPLIED+1))
    else
      # Idempotencia: si el error contiene "already exists" / "duplicate key" → no fatal
      if echo "$OUTPUT" | grep -qEi 'already exists|relation .* does exist|duplicate key|constraint .* already'; then
        log "  ⚠️  Idempotent skip: $base (relation/index/data already present)"
        SKIPPED=$((SKIPPED+1))
      else
        log "❌ FATAL $base — exit code $RC"
        echo "$OUTPUT"
        exit 1
      fi
    fi
  done
else
  log "ℹ️ migrations/sql folder not present. Skipping DB migrations."
fi

echo ""
log "=== Migrations done ==="
log "Total SQL files:  $TOTAL"
log "Applied cleanly:   $APPLIED"
log "Idempotent skips:  $SKIPPED"
log ""
exit 0
