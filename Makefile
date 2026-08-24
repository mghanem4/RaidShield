SHELL := /bin/sh

.PHONY: setup content-model content-smoke semantic-model semantic-smoke keys migrate backend frontend dev test lint format typecheck build e2e demo clean

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e 'backend[dev]'
	cd frontend && npm install

content-model:
	.venv/bin/pip install -e 'backend[content-ai]'
	cd backend && ../.venv/bin/python scripts/cache_content_model.py

content-smoke:
	cd backend && ../.venv/bin/python scripts/smoke_content_model.py

semantic-model:
	.venv/bin/pip install -e 'backend[content-ai]'
	cd backend && ../.venv/bin/python scripts/cache_semantic_model.py

semantic-smoke:
	cd backend && ../.venv/bin/python scripts/smoke_semantic_model.py

keys:
	@echo "PSEUDONYMIZATION_KEY=$$(openssl rand -hex 32)"
	@echo "DATA_ENCRYPTION_KEY=$$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

migrate:
	cd backend && ../.venv/bin/alembic upgrade head

backend: migrate
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Run 'make backend' and 'make frontend' in separate terminals."

test:
	cd backend && ../.venv/bin/pytest
	cd frontend && npm test

lint:
	cd backend && ../.venv/bin/ruff check .
	cd frontend && npm run lint

format:
	cd backend && ../.venv/bin/ruff format .
	cd frontend && npx prettier --write .

format-check:
	cd backend && ../.venv/bin/ruff format --check .
	cd frontend && npm run format:check

typecheck:
	cd backend && ../.venv/bin/mypy app
	cd frontend && npx tsc -b --pretty false

build:
	cd frontend && npm run build

e2e:
	cd frontend && npx playwright test

demo:
	curl -sS -X POST http://127.0.0.1:8000/api/v1/replay -H "Authorization: Bearer $$ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"fixture":"reply_thread_burst","speed":0,"reset_before_replay":true}'

clean:
	@echo "Use the Settings > Safety UI or authenticated DELETE /api/v1/admin/data for recoverability and explicit confirmation."
