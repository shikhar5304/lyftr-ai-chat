.PHONY: up down logs test build

up:
	docker compose up --build

up-d:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && pytest -v

build:
	docker compose build
