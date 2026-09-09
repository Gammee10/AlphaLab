# AlphaLab build surface (AGENTS.md §5). CI runs these; local Windows dev without
# `make` can run the equivalent commands directly (see backend/README.md).
PY ?= .venv/Scripts/python.exe
BACKEND = backend

.PHONY: test test-core typecheck purity dev-api dev-web codegen migrate

test:
	$(PY) -m pytest $(BACKEND)/tests -q

test-core:
	$(PY) -m pytest $(BACKEND)/tests/test_purity.py -q
	$(PY) -m pytest $(BACKEND)/tests -q -k "not slow"

typecheck:
	cd $(BACKEND) && ../$(PY) -m mypy alphalab_contracts alphalab_core

purity:
	$(PY) -m pytest $(BACKEND)/tests/test_purity.py -q

dev-api:
	$(PY) -m uvicorn alphalab_api:app --host 127.0.0.1 --port 4100

dev-web:
	npm --prefix web run dev

codegen:
	$(PY) backend/scripts/codegen.py

migrate:
	$(PY) -m alembic upgrade head
