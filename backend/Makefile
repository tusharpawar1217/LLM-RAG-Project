# AskDocs Backend Makefile

.PHONY: help install dev test test-module2 test-module3 test-module4 test-isolation lint format check migrations upgrade downgrade clean docker-build docker-up docker-down logs demo demo-module3 demo-module4 init-test worker

# Default target
help:
	@echo "Available targets:"
	@echo "  install       - Install dependencies"
	@echo "  dev           - Run development server"
	@echo "  worker        - Run ARQ background worker"
	@echo "  test          - Run tests"
	@echo "  test-module2  - Run Module 2 comprehensive tests"
	@echo "  test-module3  - Run Module 3 ingestion tests"
	@echo "  test-module4  - Run Module 4 retrieval & generation tests"
	@echo "  test-isolation- Run tenant isolation tests (critical)"
	@echo "  lint          - Run linting (ruff, mypy)"
	@echo "  format        - Format code (black, ruff)"
	@echo "  check         - Run all checks (lint, test)"
	@echo "  migrations    - Generate database migrations"
	@echo "  upgrade       - Apply database migrations"
	@echo "  downgrade     - Rollback database migrations"
	@echo "  clean         - Clean temporary files"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-up     - Start Docker services"
	@echo "  docker-down   - Stop Docker services"
	@echo "  logs          - Show Docker logs"
	@echo "  demo          - Run Module 2 demo"
	@echo "  demo-module3  - Run Module 3 demo"
	@echo "  demo-module4  - Run Module 4 demo"
	@echo "  init-test     - Initialize DB and run basic tests"

# Development
install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	python app/worker.py

# Testing
test:
	pytest -v --cov=app

test-module2:
	python run_module2_tests.py

test-module3:
	pytest tests/test_ingestion/ -v -s

test-module4:
	pytest tests/test_generation/ tests/test_retrieval/ -v -s

test-isolation:
	pytest tests/test_tenant_isolation.py -v -s

test-watch:
	pytest-watch --runner "pytest -v --cov=app"

# Code Quality
lint:
	ruff check app tests
	mypy app --ignore-missing-imports

format:
	black app tests
	ruff format app tests

check: lint test

# Database
migrations:
	alembic revision --autogenerate -m "$(name)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

# Docker
docker-build:
	docker build -t askdocs-backend .

docker-up:
	cd .. && docker compose up -d

docker-down:
	cd .. && docker compose down

docker-logs:
	cd .. && docker compose logs -f

# Demo & Testing
demo:
	cd .. && python demo_module2.py

demo-module3:
	python demo_module3.py

demo-module4:
	python demo_module4.py

init-test:
	python init_and_test.py

# Utilities
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov/

# Pre-commit
install-hooks:
	pre-commit install

run-hooks:
	pre-commit run --all-files

# Setup
setup:
	python setup_dev.py