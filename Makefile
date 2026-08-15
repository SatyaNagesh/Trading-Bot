.PHONY: install lint test run clean

install:
	poetry install

lint:
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run mypy packages/ services/

lint-fix:
	poetry run ruff check --fix .
	poetry run ruff format .

test:
	poetry run pytest tests/ -x --cov=packages

test-all:
	poetry run pytest tests/ -x --cov=packages --cov=services --cov=apps

run-api:
	poetry run uvicorn services.api.main:app --reload --port 8000

run-discord:
	poetry run python -m services.discord_bot.main

run-docs:
	poetry run mkdocs serve

docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-build:
	docker compose -f docker/docker-compose.yml build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
	find . -type f -name "*.pyc" -delete 2>/dev/null
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov coverage dist build
