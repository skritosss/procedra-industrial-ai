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

.PHONY: venv env install run video-worker video-job-contention test lint typecheck compile pip-check static-smoke public-scope-audit public-content-audit safety-eval quality-discrimination demo-eval partner-demo-pack cleanup-plan cleanup-delete db-migrate db-verify db-backup db-restore document-ownership-plan document-ownership-apply smoke api-smoke health ready ready-details metrics docker-build docker-config docker-up docker-down

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

video-worker:
	$(APP_PYTHON) scripts/run_video_job_worker.py

video-job-contention:
	$(APP_PYTHON) scripts/run_video_job_contention_probe.py

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

static-smoke:
	$(APP_PYTHON) scripts/static_asset_smoke.py

public-scope-audit:
	$(APP_PYTHON) scripts/public_scope_audit.py --sample-limit 0

public-content-audit:
	$(APP_PYTHON) scripts/public_content_audit.py

safety-eval:
	$(APP_PYTHON) scripts/run_safety_eval.py

quality-discrimination:
	$(APP_PYTHON) scripts/run_quality_discrimination.py

demo-eval:
	$(APP_PYTHON) scripts/run_demo_eval.py

partner-demo-pack:
	$(APP_PYTHON) scripts/build_partner_demo_pack.py

cleanup-plan:
	$(APP_PYTHON) scripts/cleanup_artifacts.py --max-age-hours $(CLEANUP_MAX_AGE_HOURS) --reconcile-video-ownership

cleanup-delete:
	$(APP_PYTHON) scripts/cleanup_artifacts.py --max-age-hours $(CLEANUP_MAX_AGE_HOURS) --reconcile-video-ownership --delete

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

smoke: compile lint typecheck static-smoke public-scope-audit public-content-audit safety-eval quality-discrimination test pip-check docker-config api-smoke

api-smoke:
	$(APP_PYTHON) -c "from fastapi.testclient import TestClient; from app.main import app; client = TestClient(app); assert client.get('/health').status_code == 200; response = client.post('/api/instructions/generate', json={'task': 'Подготовить рабочее место оператора перед запуском оборудования'}); assert response.status_code == 200"

health:
	curl -fsS http://$(HOST):$(PORT)/health

ready:
	curl -fsS http://$(HOST):$(PORT)/ready

ready-details:
	@test -n "$(API_ACCESS_TOKEN)" || (echo "API_ACCESS_TOKEN is required for ready-details" && exit 2)
	curl -fsS -H "Authorization: Bearer $(API_ACCESS_TOKEN)" http://$(HOST):$(PORT)/ready/details

metrics:
	@test -n "$(API_ACCESS_TOKEN)" || (echo "API_ACCESS_TOKEN is required for metrics unless demo mode explicitly enables METRICS_PUBLIC_ENABLED=true" && exit 2)
	curl -fsS -H "Authorization: Bearer $(API_ACCESS_TOKEN)" http://$(HOST):$(PORT)/metrics

docker-build:
	docker build -t $(IMAGE) .

docker-config:
	docker compose config

docker-up:
	docker compose up --build

docker-down:
	docker compose down
