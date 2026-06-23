PYTHON ?= python3.12
VENV ?= .venv
APP_PYTHON := $(VENV)/bin/python
HOST ?= 127.0.0.1
PORT ?= 8000
IMAGE ?= industrial-instruction-ai:local
CLEANUP_MAX_AGE_HOURS ?= 24
DATABASE ?= generated/app.sqlite3
BACKUP ?=
SAFETY_BACKUP ?=

.PHONY: venv env install run test lint typecheck compile pip-check demo-eval partner-demo-pack cleanup-plan cleanup-delete db-migrate db-verify db-backup db-restore document-ownership-plan document-ownership-apply smoke api-smoke health ready metrics docker-build docker-config docker-up docker-down

venv:
	$(PYTHON) -m venv $(VENV)

.env.local:
	cp .env.example .env.local

env: .env.local

install: venv env
	$(APP_PYTHON) -m pip install --upgrade pip
	$(APP_PYTHON) -m pip install -r requirements.txt

run:
	$(APP_PYTHON) -m uvicorn app.main:app --host $(HOST) --port $(PORT)

test:
	$(APP_PYTHON) -m pytest

lint:
	$(APP_PYTHON) -m ruff check app tests scripts

typecheck:
	$(APP_PYTHON) -m mypy app scripts

compile:
	$(APP_PYTHON) -m compileall -q app tests scripts

pip-check:
	$(APP_PYTHON) -m pip check

demo-eval:
	$(APP_PYTHON) scripts/run_demo_eval.py

partner-demo-pack:
	$(APP_PYTHON) scripts/build_partner_demo_pack.py

cleanup-plan:
	$(APP_PYTHON) scripts/cleanup_artifacts.py --max-age-hours $(CLEANUP_MAX_AGE_HOURS)

cleanup-delete:
	$(APP_PYTHON) scripts/cleanup_artifacts.py --max-age-hours $(CLEANUP_MAX_AGE_HOURS) --delete

db-migrate:
	$(APP_PYTHON) scripts/manage_database.py migrate --database "$(DATABASE)"

db-verify:
	$(APP_PYTHON) scripts/manage_database.py verify --database "$(DATABASE)"

db-backup:
	$(APP_PYTHON) scripts/manage_database.py backup --database "$(DATABASE)" $(if $(BACKUP),--output "$(BACKUP)",)

db-restore:
	@test -n "$(BACKUP)" || (echo "BACKUP=/path/to/backup.sqlite3 is required" && exit 2)
	$(APP_PYTHON) scripts/manage_database.py restore --database "$(DATABASE)" --source "$(BACKUP)" $(if $(SAFETY_BACKUP),--safety-backup "$(SAFETY_BACKUP)",)

document-ownership-plan:
	$(APP_PYTHON) scripts/reconcile_document_ownership.py --database "$(DATABASE)"

document-ownership-apply:
	$(APP_PYTHON) scripts/reconcile_document_ownership.py --database "$(DATABASE)" --apply

smoke: compile lint typecheck test pip-check docker-config api-smoke

api-smoke:
	$(APP_PYTHON) -c "from fastapi.testclient import TestClient; from app.main import app; client = TestClient(app); assert client.get('/health').status_code == 200; response = client.post('/api/instructions/generate', json={'task': 'Подготовить рабочее место оператора перед запуском оборудования'}); assert response.status_code == 200"

health:
	curl -fsS http://$(HOST):$(PORT)/health

ready:
	curl -fsS http://$(HOST):$(PORT)/ready

metrics:
	curl -fsS http://$(HOST):$(PORT)/metrics

docker-build:
	docker build -t $(IMAGE) .

docker-config:
	docker compose config

docker-up:
	docker compose up --build

docker-down:
	docker compose down
