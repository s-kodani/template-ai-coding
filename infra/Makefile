.PHONY: network langfuse-up langfuse-down app-up app-down langflow-up langflow-down up down seed test

# make -C infra から呼ばれる前提。パスは Makefile 基準で解決する。
INFRA_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
ROOT := $(abspath $(INFRA_DIR)/..)

network:
	docker network inspect observability >/dev/null 2>&1 || docker network create observability

langfuse-up: network
	docker compose -f $(INFRA_DIR)langfuse/docker-compose.yml -f $(INFRA_DIR)langfuse/network.yml --env-file $(INFRA_DIR)langfuse/.env up -d

langfuse-down:
	docker compose -f $(INFRA_DIR)langfuse/docker-compose.yml -f $(INFRA_DIR)langfuse/network.yml down

app-up: network
	docker compose -f $(INFRA_DIR)app/compose.yml --env-file $(ROOT)/.env up -d --build

app-down:
	docker compose -f $(INFRA_DIR)app/compose.yml down

langflow-up:
	docker compose -f $(INFRA_DIR)langflow/compose.yml --env-file $(ROOT)/.env up -d

langflow-down:
	docker compose -f $(INFRA_DIR)langflow/compose.yml down

up: langfuse-up app-up

down: app-down langfuse-down

seed:
	cd $(ROOT) && uv run python scripts/seed.py

test:
	cd $(ROOT) && uv run pytest
