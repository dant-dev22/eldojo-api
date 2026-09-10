#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================="
echo " ElDojo BACKEND Full Deploy (1 comando)"
echo " Root: $PROJECT_ROOT"
echo "============================================="
echo ""

chmod +x "$SCRIPT_DIR"/0[0-2]-*.sh

SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"

# Paso 0 (opcional skip): Actualizar git a último commit master
if [ "$SKIP_GIT_PULL" != "1" ]; then
  echo ""
  echo "⏩ [Paso 0/2] git pull origin master (para skipear: SKIP_GIT_PULL=1 bash scripts/deploy/deploy.sh)"
  "$SCRIPT_DIR/00-pull-git.sh"
else
  echo "ℹ️  SKIP_GIT_PULL=1: omitimos pull de git (se supone que ya corriste scripts/deploy/00-pull-git.sh)."
fi

# Paso 1: DB migrations (idempotente)
"$SCRIPT_DIR/01-migrate-db.sh"

# Paso 2: API warm-start deploy
"$SCRIPT_DIR/02-deploy-api.sh"

echo ""
echo "✅ BACKEND deploy completo."
