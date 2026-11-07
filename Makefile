# One command per output (docs/CONTRACTS.md). Targets for pipelines not yet built print a note.
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python)

.PHONY: schema load a c d e pitch app all test snapshot v2 fixtures openapi api web v2-check

schema:            ## create the four shared tables in NAVIGATOR_DB
	$(PY) -m src.lineage

load: schema       ## raw_* and task_* tables from the pack
	$(PY) -m src.load

a: load            ## Track A: detectors, corrections, A1 + A2 CSVs
	@if [ -f src/a_pipeline.py ]; then $(PY) -m src.a_pipeline; else echo "make a: not built yet (#7-#12)"; fi

c: load            ## Track C: features, yield model, C1 + C2 CSVs, C3 € risk
	@if [ -f src/c_pipeline.py ]; then $(PY) -m src.c_pipeline; else echo "make c: not built yet (#14-#19)"; fi

d: a               ## Track D1: catchment P/N loads to water + SBTN-style priority → D1 CSV
	$(PY) -m src.d_nature

e:                 ## Track E: copilot answers CSV
	@if [ -f src/e_answers.py ]; then $(PY) -m src.e_answers; else echo "make e: not built yet (#22-#23)"; fi

pitch:             ## fill every {{placeholder}} in METHOD_NOTE + docs/pitch from results → out/pitch/
	$(PY) -m src.story_fill

app:               ## Streamlit app (stop it before `make all`: it holds the DuckDB lock)
	@if [ -f app/Home.py ]; then $(PY) -m streamlit run app/Home.py; else echo "make app: not built yet (#20)"; fi

all: load a c d e pitch   ## every submission file + pitch values from the unzipped pack (~1 min)

test:
	$(PY) -m pytest -q

# ── v2 (docs/V2_ARCHITECTURE.md "Run it"); never runs make a/c/e, reads only out/serve.duckdb ──
snapshot:          ## out/navigator.duckdb → out/serve.duckdb (the frozen v1 data v2 reads)
	$(PY) -m src.serve_db

v2:                ## presets, weather frames, catalog → out/v2/ (layers that aren't built yet print a note)
	@for m in p_presets p_weather r_catalog; do \
	  if [ -f src/$$m.py ]; then $(PY) -m src.$$m || exit 1; else echo "make v2: src/$$m.py not built yet"; fi; done

fixtures:          ## rebuild api/fixtures/*.json from serve.duckdb (mock values; committed)
	$(PY) -m api.fixtures_build

openapi:           ## api/schemas.py → web/src/api/openapi.json (web: npm run gen:types)
	$(PY) -m api.export_openapi

api:               ## FastAPI on :8000 (API_MOCK=1 make api serves the fixtures)
	$(PY) -m uvicorn api.main:app --port 8000 --reload

web:               ## React app on :5173, proxies /api → :8000
	@if [ -f web/package.json ]; then cd web && npm install && npm run dev; else echo "make web: not built yet (#88)"; fi

v2-check:          ## v2 tests + the web build/typecheck when web/ exists
	$(PY) -m pytest -q tests/test_api_contract.py tests/test_v2_guard.py $$(ls tests/test_p_*.py tests/test_r_*.py 2>/dev/null)
	@if [ -f web/package.json ]; then cd web && npm ci && npm run build && npx tsc --noEmit; fi
