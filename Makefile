# AlphaLab build surface (AGENTS.md §5). CI runs these; local Windows dev without
# `make` can run the equivalent commands directly (see backend/README.md).
PY ?= .venv/Scripts/python.exe
BACKEND = backend

.PHONY: test test-core typecheck purity dev-api dev-web codegen migrate test-web

test:
	$(PY) -m pytest $(BACKEND)/tests -q

test-web:
	npm --prefix web run test

test-core:
	$(PY) -m pytest $(BACKEND)/tests/test_purity.py -q
	$(PY) -m pytest $(BACKEND)/tests -q -k "not slow"

typecheck:
	cd $(BACKEND) && ../$(PY) -m mypy alphalab_contracts alphalab_core alphalab_marketdata alphalab_store alphalab_api alphalab_ai

purity:
	$(PY) -m pytest $(BACKEND)/tests/test_purity.py -q

dev-api:
	cd $(BACKEND) && ../$(PY) -m uvicorn alphalab_api.app:create_app --factory --host 127.0.0.1 --port 4100

dev-web:
	npm --prefix web run dev

codegen:
	$(PY) backend/scripts/codegen.py

migrate:
	cd $(BACKEND) && ../$(PY) -m alphalab_store.database
