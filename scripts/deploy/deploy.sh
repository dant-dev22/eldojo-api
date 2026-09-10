#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "============================================="
echo " ElDojo BACKEND Full Deploy (1 comando)"
echo " Root: $PROJECT_ROOT"
echo "============================================="
echo ""

chmod +x "$SCRIPT_DIR"/01-*.sh "$SCRIPT_DIR"/02-*.sh

# Paso 1: DB migrations (idempotente)
"$SCRIPT_DIR/01-migrate-db.sh"

# Paso 2: API warm-start deploy
"$SCRIPT_DIR/02-deploy-api.sh"

echo ""
echo "✅ BACKEND deploy completo."
