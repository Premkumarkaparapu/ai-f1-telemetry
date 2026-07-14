.PHONY: install ingest run test lint format clean

# ── Setup ────────────────────────────────────────────────────────────────────
install:
	pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# ── Data Pipeline ─────────────────────────────────────────────────────────────
ingest:
	python -m data_pipeline.load_db

verify:
	python -m data_pipeline.verify

# ── Backend ───────────────────────────────────────────────────────────────────
init-db:
	python -m backend.app.database.init_db

run:
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v -m "not integration"

test-integration:
	pytest tests/ -v -m "integration"

test-all:
	pytest tests/ -v

# ── Code Quality ──────────────────────────────────────────────────────────────
lint:
	flake8 backend/ data_pipeline/ ml/ tests/ --max-line-length=100

format:
	black backend/ data_pipeline/ ml/ tests/ --line-length=100
	isort backend/ data_pipeline/ ml/ tests/

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -f f1_telemetry.db
	rm -rf logs/*.log
