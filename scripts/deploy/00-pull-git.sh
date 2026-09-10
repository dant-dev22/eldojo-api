#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================="
echo " ElDojo BACKEND — Actualizar Git (pull only)"
echo " Root:   $PROJECT_ROOT"
echo " Branch: master (default)"
echo "============================================="
echo ""

if ! command -v git >/dev/null 2>&1; then
  echo "❌ git no está instalado en este VPS. Instálalo primero: apt-get install -y git" >&2
  exit 1
fi

DEFAULT_BRANCH="master"

if [ -n "${ELDOJO_FORCE_BRANCH:-}" ]; then
  DEFAULT_BRANCH="$ELDOJO_FORCE_BRANCH"
  echo "ℹ️  Usando branch override ELDOJO_FORCE_BRANCH=$DEFAULT_BRANCH"
fi

ORIGIN_REMOTE="origin"

if ! git remote get-url "$ORIGIN_REMOTE" >/dev/null 2>&1; then
  echo "❌ No existe el remote '$ORIGIN_REMOTE'. Configuralo primero con:" >&2
  echo "   git remote add origin git@github.com:dant-dev22/eldojo-api.git" >&2
  exit 2
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD || true)"
if [ "$CURRENT_BRANCH" != "$DEFAULT_BRANCH" ]; then
  echo "ℹ️  Checkout forzado a $DEFAULT_BRANCH (estabas en '$CURRENT_BRANCH')"
  git checkout "$DEFAULT_BRANCH"
fi

echo "→ git fetch $ORIGIN_REMOTE --prune"
git fetch "$ORIGIN_REMOTE" --prune --tags

echo ""
echo "→ git pull $ORIGIN_REMOTE $DEFAULT_BRANCH --ff-only"
git pull --ff-only "$ORIGIN_REMOTE" "$DEFAULT_BRANCH"

LATEST="$(git log -1 --pretty=format:'%h %ad — %s [%an]' --date=short)"
HEAD_BEFORE_UPSTREAM="${BEFORE_COMMIT:-}"
if [ -n "$HEAD_BEFORE_UPSTREAM" ] && [ "$HEAD_BEFORE_UPSTREAM" != "$(git rev-parse --short HEAD)" ]; then
  echo "✅ Se actualizó desde $HEAD_BEFORE_UPSTREAM hasta $(git rev-parse --short HEAD)."
fi
echo ""
echo "Último commit actual en $DEFAULT_BRANCH:"
echo "   $LATEST"
echo ""
echo "✅ Git actualizado OK."
