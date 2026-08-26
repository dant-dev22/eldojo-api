.PHONY: help install venv start start-no-reload health db-check docs clean lint-check db-reset db-migrate db-seed db-teardown db-status db-up

.DEFAULT_GOAL := help

SHELL := /bin/bash

PROJECT_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
INFRA_ROOT   := $(abspath $(PROJECT_ROOT)/../eldojo)
INFRA_COMPOSE:= docker compose -f $(INFRA_ROOT)/docker-compose.local.yml

ifeq ($(OS),Windows_NT)
    VENV_PY := $(or $(wildcard $(PROJECT_ROOT).venv/Scripts/python.exe),$(wildcard $(PROJECT_ROOT)venv/Scripts/python.exe),python)
    VENV_UVICORN := $(or $(wildcard $(PROJECT_ROOT).venv/Scripts/uvicorn.exe),$(wildcard $(PROJECT_ROOT)venv/Scripts/uvicorn.exe),uvicorn)
else
    VENV_PY := $(or $(wildcard $(PROJECT_ROOT).venv/bin/python),$(wildcard $(PROJECT_ROOT)venv/bin/python),python3)
    VENV_UVICORN := $(or $(wildcard $(PROJECT_ROOT).venv/bin/uvicorn),$(wildcard $(PROJECT_ROOT)venv/bin/uvicorn),uvicorn)
endif

_MANUAL_MIGRATIONS_ALL := \
	manual_migration_20260720_add_user_names.sql \
	manual_migration_20260727_add_user_first_time.sql \
	manual_migration_20260729_add_academy_email_verification.sql \
	manual_migration_20260730_add_academy_pending_sessions.sql \
	manual_migration_20260805_add_session_sync_tickets.sql \
	manual_migration_20260806_add_belts_system.sql \
	manual_migration_20260806_add_trajectory_events.sql \
	manual_migration_20260807_add_student_sports_record.sql \
	manual_migration_20260807_add_student_fight_records.sql \
	manual_migration_20260807_student_enrichment.sql \
	manual_migration_20260821_seed_belts_all_orgs.sql

_MANUAL_SEEDS_ALL := \
	manual_seed_prod_demo_01_verify_target.sql \
	manual_seed_prod_demo_02_cleanup.sql \
	manual_seed_prod_demo_03_seed_classes.sql \
	manual_seed_prod_demo_04_seed_students.sql \
	manual_seed_prod_demo_05_seed_activity.sql \
	manual_seed_prod_demo_06_fix_attendance.sql

MANUAL_MIGRATIONS := $(wildcard $(addprefix $(PROJECT_ROOT),$(_MANUAL_MIGRATIONS_ALL)))
MANUAL_SEEDS      := $(wildcard $(addprefix $(PROJECT_ROOT),$(_MANUAL_SEEDS_ALL)))

help:
	@echo "Available commands:"
	@echo "  make help            - Show this help (default target)"
	@echo "  make install         - Create venv and install backend dependencies"
	@echo "  make venv            - Create virtual environment only (.venv)"
	@echo "  make start           - Run FastAPI dev server (uvicorn --reload) on port 8000"
	@echo "  make start-no-reload - Run FastAPI server without hot-reload"
	@echo "  make health          - GET /api/v1/health (curl localhost:8000)"
	@echo "  make db-check        - GET /api/v1/health/db (curl localhost:8000)"
	@echo "  make db-status       - docker compose ps for local infra"
	@echo "  make db-up           - Start ONLY the local MySQL container + wait healthy (no teardown, no migrations, no seeds)"
	@echo "  make db-teardown     - stop + delete local mysql container + volume"
	@echo "  make db-reset        - WIPE DB: teardown + create + alembic + migrations + seeds"
	@echo "  make db-migrate      - Apply Alembic head + existing manual migrations (skips missing files)"
	@echo "  make db-seed         - Seed master data + existing demo seeds (skips missing files)"
	@echo "  make docs            - Open /docs Swagger endpoint URL hint"
	@echo "  make lint-check      - Syntax check all Python files (py_compile)"
	@echo "  make clean           - Remove __pycache__, *.pyc, etc."

venv:
	@if [ ! -d "$(PROJECT_ROOT).venv" ] && [ ! -d "$(PROJECT_ROOT)venv" ]; then \
		echo "[eldojo-api] creating .venv..."; \
		"$(VENV_PY)" -m venv "$(PROJECT_ROOT).venv"; \
	fi

install: venv
	@echo "[eldojo-api] upgrading pip and installing project dependencies..."
	@"$(VENV_PY)" -m pip install --upgrade pip setuptools wheel
	@"$(VENV_PY)" -m pip install -e "$(PROJECT_ROOT)"
	@if [ ! -d "$(PROJECT_ROOT)uploads" ]; then \
		mkdir -p "$(PROJECT_ROOT)uploads"; \
	fi
	@echo "[eldojo-api] installed. Use 'make start' to run the server."

start:
	@echo "[eldojo-api] starting uvicorn (reload mode) on 0.0.0.0:8000..."
	@"$(VENV_UVICORN)" app.main:app --reload --host 0.0.0.0 --port 8000

start-no-reload:
	@echo "[eldojo-api] starting uvicorn on 0.0.0.0:8000..."
	@"$(VENV_UVICORN)" app.main:app --host 0.0.0.0 --port 8000

health:
	@curl -sS -X GET http://127.0.0.1:8000/api/v1/health || echo "[eldojo-api] is the server running? start it with 'make start'"

db-check:
	@curl -sS -X GET http://127.0.0.1:8000/api/v1/health/db || echo "[eldojo-api] is the server running? start it with 'make start'"

docs:
	@echo "[eldojo-api] Swagger UI :  http://127.0.0.1:8000/docs"
	@echo "[eldojo-api] Redoc     :  http://127.0.0.1:8000/redoc"
	@echo "[eldojo-api] Health    :  http://127.0.0.1:8000/api/v1/health"

lint-check:
	@echo "[eldojo-api] syntax-checking Python files under app/..."
	@find "$(PROJECT_ROOT)app" -name "*.py" -print0 | xargs -0 "$(VENV_PY)" -m py_compile && echo "[eldojo-api] syntax OK"

clean:
	@find "$(PROJECT_ROOT)app" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find "$(PROJECT_ROOT)app" -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "[eldojo-api] cleaned."

db-status:
	@$(INFRA_COMPOSE) ps

db-up:
	@echo "[eldojo-api-db] ensuring local mysql container is up..."
	@$(INFRA_COMPOSE) up -d mysql
	@echo "[eldojo-api-db] waiting for MySQL healthy (poll [max 90s])..."
	@"$(VENV_PY)" "$(PROJECT_ROOT)scripts_wait_mysql_healthy.py"
	@echo "[eldojo-api-db] mysql is ready. Run 'make start' to run the API server."
	@$(MAKE) --no-print-directory db-status

db-teardown:
	@echo "[eldojo-api-db] stopping and removing local mysql container + volume..."
	@-$(INFRA_COMPOSE) down -v --remove-orphans || true
	@echo "[eldojo-api-db] done."

db-migrate:
	@echo "[eldojo-api-db] step 1/2 — alembic upgrade head (repo: eldojo, cwd=$(INFRA_ROOT))"
	@cd "$(INFRA_ROOT)" && $(VENV_PY) -m alembic upgrade head
	@echo "[eldojo-api-db] step 2/2 — applying manual migrations (missing files are skipped)..."
	@if [ -z "$(MANUAL_MIGRATIONS)" ]; then \
		echo "[eldojo-api-db] no manual migration files found on disk — skipping step 2/2."; \
	else \
		$(VENV_PY) "$(PROJECT_ROOT)scripts_run_sql_files.py" \
			"$$($(VENV_PY) -c 'from app.core.config import settings; print(settings.database_url)')" \
			migration $(MANUAL_MIGRATIONS); \
	fi
	@echo "[eldojo-api-db] migrations done."

db-seed:
	@echo "[eldojo-api-db] step 1/2 — seed master (org/branch/disciplines/admin user + belts)"
	@$(VENV_PY) "$(PROJECT_ROOT)scripts/seed.py"
	@echo "[eldojo-api-db] step 2/2 — demo seeds (classes, 40 students, enrollments, payments, attendance) — missing files are skipped"
	@if [ -z "$(MANUAL_SEEDS)" ]; then \
		echo "[eldojo-api-db] no manual seed files found on disk — skipping step 2/2."; \
	else \
		$(VENV_PY) "$(PROJECT_ROOT)scripts_run_sql_files.py" \
			"$$($(VENV_PY) -c 'from app.core.config import settings; print(settings.database_url)')" \
			seed $(MANUAL_SEEDS); \
	fi
	@echo "[eldojo-api-db] seeds done. Use dantedev22@gmail.com / d4nt3r4d for local login."

db-reset: db-teardown
	@echo "[eldojo-api-db] recreating local mysql container from docker-compose.local.yml ..."
	@$(INFRA_COMPOSE) up -d
	@echo "[eldojo-api-db] waiting for MySQL healthy (poll [max 90s]) ..."
	@"$(VENV_PY)" "$(PROJECT_ROOT)scripts_wait_mysql_healthy.py"
	@$(MAKE) --no-print-directory db-migrate
	@$(MAKE) --no-print-directory db-seed
	@echo "[eldojo-api-db] reset complete. Run 'make start' to run the API server."
