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

# ================ 1) PRIORIDAD MÁXIMA: DATABASE_URL PARSER (dialecto autodetect) ================
DIALECT="unknown"
DB_USER=""
DB_PASS=""
DB_HOST=""
DB_PORT=""
DB_NAME=""

if [[ -n "${DATABASE_URL:-}" ]]; then
  URL="${DATABASE_URL}"
  log "Parsing DATABASE_URL (dialecto auto-detect)"

  # 1.1) Extraer SCHEMA (hasta ://)
  SCHEME="${URL%%://*}"
  REST="${URL#*://}"
  case "$SCHEME" in
    mysql*|mariadb*) DIALECT="mysql" ;;
    postgres*|postgresql*) DIALECT="postgres" ;;
    *) log "WARN: scheme=$SCHEME desconocido; se intenta por vars DATABASE_* legacy" ;;
  esac
  log "  scheme=$SCHEME → dialect=$DIALECT"

  # 1.2) Split user:pass@host:port/dbname
  if [[ "$REST" == *"@"* ]]; then
    CRED="${REST%%@*}"
    HOSTPORT_DB="${REST##*@}"
    if [[ "$CRED" == *":"* ]]; then
      DB_USER="${CRED%%:*}"
      DB_PASS="${CRED#*:}"
    else
      DB_USER="${CRED}"
    fi
  else
    HOSTPORT_DB="${REST}"
  fi

  # 1.3) Split host:port vs dbname
  if [[ "$HOSTPORT_DB" == *"/"* ]]; then
    HOSTPORT="${HOSTPORT_DB%%/*}"
    DB_NAME="${HOSTPORT_DB#*/}"
    # limpiar ?query params al final
    DB_NAME="${DB_NAME%%\?*}"
  else
    HOSTPORT="${HOSTPORT_DB}"
  fi

  # 1.4) host : port
  if [[ "$HOSTPORT" == *":"* ]]; then
    DB_HOST="${HOSTPORT%%:*}"
    DB_PORT="${HOSTPORT##*:}"
  else
    DB_HOST="${HOSTPORT}"
    if [[ "$DIALECT" == "mysql" ]]; then DB_PORT="3306"; else DB_PORT="5432"; fi
  fi

  # 1.5) Mostrar preview (NUNCA passwords completos)
  lenp=${#DB_PASS}
  if (( lenp > 4 )); then
    pass_preview="${DB_PASS:0:2}...${DB_PASS: -2} (len=$lenp)"
  else
    pass_preview="**** (len=$lenp)"
  fi
  log "  user=$DB_USER pass=$pass_preview host=$DB_HOST port=$DB_PORT db=$DB_NAME"
fi

# ================ 2) FALLBACK: Legacy DATABASE_* / POSTGRES_* si DATABASE_URL no resolvió dialecto ================
if [[ "$DIALECT" == "unknown" ]]; then
  log "DATABASE_URL no usable → fallback vars legacy"
  DB_HOST="${DATABASE_HOST:-${POSTGRES_HOST:-localhost}}"
  DB_PORT="${DATABASE_PORT:-${POSTGRES_PORT:-5432}}"
  DB_USER="${DATABASE_USER:-${POSTGRES_USER:-eldojo}}"
  DB_NAME="${DATABASE_NAME:-${POSTGRES_DB:-${POSTGRES_DATABASE:-eldojo}}}"
  DB_PASS="${DATABASE_PASSWORD:-${POSTGRES_PASSWORD:-}}"
  # Si $DATABASE_PORT == 3306 o existe DATABASE_URL (caído aquí) → mysql si port==3306
  if [[ "$DB_PORT" == "3306" || -n "${MYSQL_PWD:-}" ]]; then DIALECT="mysql"; else DIALECT="postgres"; fi
  log "  (fallback) dialect=$DIALECT host=$DB_HOST port=$DB_PORT user=$DB_USER db=$DB_NAME"
fi

# ================ 3) Cliente CLI ================
execute_sql_file() {
  local f="$1"
  if [[ "$DIALECT" == "mysql" ]]; then
    command -v mysql >/dev/null 2>&1 || { log "FATAL: mysql client not installed. apt-get install -y mysql-client"; exit 1; }
    export MYSQL_PWD="$DB_PASS"
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -D "$DB_NAME" --connect-timeout=10 --default-character-set=utf8mb4 2>&1 < "$f"
  else
    command -v psql >/dev/null 2>&1 || { log "FATAL: psql client not installed. apt-get install -y postgresql-client"; exit 1; }
    export PGHOST="$DB_HOST" PGPORT="$DB_PORT" PGUSER="$DB_USER" PGDATABASE="$DB_NAME" PGPASSWORD="$DB_PASS"
    psql -v ON_ERROR_STOP=1 -f "$f" 2>&1
  fi
}

# ================ 4) Ejecutar todas las migraciones SQL ordenadas ================
TOTAL=0
APPLIED=0
SKIPPED=0
if [[ -d "$MIGRATIONS_DIR" ]]; then
  shopt -s nullglob
  mapfile -t SQL_FILES < <(find "$MIGRATIONS_DIR" -maxdepth 1 -type f -name '*.sql' | sort)
  shopt -u nullglob

  TOTAL=${#SQL_FILES[@]}
  log "Found $TOTAL migration SQL files in $MIGRATIONS_DIR (dialect=$DIALECT)"

  for sql_file in "${SQL_FILES[@]}"; do
    base="$(basename "$sql_file")"
    log "▶ Applying: $base"
    set +e
    OUTPUT=$(execute_sql_file "$sql_file")
    RC=$?
    set -e
    if [[ $RC -eq 0 ]]; then
      log "  ✅ OK $base"
      APPLIED=$((APPLIED+1))
    else
      if echo "$OUTPUT" | grep -qEi 'already exists|Duplicate entry|Duplicate column name|duplicate key|constraint.*already|does exist|Table .* already exists|Can.*t create|for key.*exists|Duplicate.*key name'; then
        log "  ⚠️  Idempotent skip: $base (already present, nothing new)"
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

# Limpiar secrets envs de passwords
unset MYSQL_PWD PGPASSWORD DB_PASS 2>/dev/null || true

echo ""
log "=== Migrations done ==="
log "Dialect DB:      $DIALECT"
log "Total SQL:       $TOTAL"
log "Applied cleanly:   $APPLIED"
log "Idempotent skips: $SKIPPED"
log ""
exit 0
