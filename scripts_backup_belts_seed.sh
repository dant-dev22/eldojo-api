#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="${SCRIPT_DIR}/backups/belts_seed_${TS}"
LOG="${OUT}/backup.log"
mkdir -p "$OUT" && touch "$LOG"
echo "=== BACKUP BELTS SEED $TS ==="
DU=""; DP=""; DH="localhost"; DPT="3306"; DN=""
while IFS='=' read -r K V; do
  K="${K// /}"; V="${V#\"}"; V="${V%\"}"; V="${V#\'}"; V="${V%\'}"
  case "$K" in
    MYSQL_USER|DATABASE_USER|DB_USER)          DU="$V" ;;
    MYSQL_PASSWORD|DATABASE_PASSWORD|DB_PASSWORD) DP="$V" ;;
    MYSQL_HOST|DATABASE_HOST|DB_HOST)          DH="$V" ;;
    MYSQL_PORT|DATABASE_PORT|DB_PORT)          DPT="$V" ;;
    MYSQL_DB|MYSQL_DATABASE|DATABASE_NAME|DB_NAME) DN="$V" ;;
  esac
done < <(grep -Ev '^\s*(#|$)' "$ENV_FILE")
[ -z "$DU" ] || [ -z "$DP" ] || [ -z "$DN" ] && { echo "FAIL: vars BD incompletas en $ENV_FILE"; exit 1; }
echo "  $DH:$DPT / $DN / $DU" | tee -a "$LOG"
TABS="belt_levels belt_stripes student_belt_histories students organizations"
echo "[1/3] check tablas" | tee -a "$LOG"
for T in $TABS; do
  E="$(MYSQL_PWD="$DP" mysql -h"$DH" -P"$DPT" -u"$DU" "$DN" -N -e "SHOW TABLES LIKE '${T}';" 2>>"$LOG" || true)"
  echo "  $T -> ${E:-FALTA}" | tee -a "$LOG"
done
echo "[2/3] conteos" | tee -a "$LOG"
for T in $TABS; do
  C="$(MYSQL_PWD="$DP" mysql -h"$DH" -P"$DPT" -u"$DU" "$DN" -N -e "SELECT COUNT(*) FROM ${T};" 2>>"$LOG" || echo "?")"
  echo "  $T : $C" | tee -a "$LOG"
done
echo "[3/3] dumps" | tee -a "$LOG"
DF="${OUT}/dump_pre_seed_belts.sql"
MYSQL_PWD="$DP" mysqldump -h"$DH" -P"$DPT" -u"$DU" --single-transaction --routines --triggers --quick "$DN" $TABS > "$DF" 2>>"$LOG"
gzip -f "$DF" && echo "  belts OK: $(du -h ${DF}.gz|cut -f1)" | tee -a "$LOG"
FD="${OUT}/dump_fulldb_pre_seed.sql"
if MYSQL_PWD="$DP" mysqldump -h"$DH" -P"$DPT" -u"$DU" --single-transaction --routines --triggers --quick "$DN" > "$FD" 2>>"$LOG"; then
  gzip -f "$FD" && echo "  full  OK: $(du -h ${FD}.gz|cut -f1)" | tee -a "$LOG"
else
  rm -f "$FD"; echo "  (full skip)" | tee -a "$LOG"
fi
echo "=== DONE: $OUT ==="
echo "RESTORE: cd $OUT ; gunzip dump_pre_seed_belts.sql.gz ; mysql -h$DH -P$DPT -u$DU -p $DN < dump_pre_seed_belts.sql"
