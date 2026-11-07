# One command per output (docs/CONTRACTS.md). Targets for pipelines not yet built print a note.
PY := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python)

.PHONY: schema load a c e pitch app all test

schema:            ## create the four shared tables in NAVIGATOR_DB
	$(PY) -m src.lineage

load: schema       ## raw_* and task_* tables from the pack
	$(PY) -m src.load

a: load            ## Track A: detectors, corrections, A1 + A2 CSVs
	@if [ -f src/a_pipeline.py ]; then $(PY) -m src.a_pipeline; else echo "make a: not built yet (#7-#12)"; fi

c: load            ## Track C: features, yield model, C1 + C2 CSVs, C3 € risk
	@if [ -f src/c_pipeline.py ]; then $(PY) -m src.c_pipeline; else echo "make c: not built yet (#14-#19)"; fi

e:                 ## Track E: copilot answers CSV
	@if [ -f src/e_answers.py ]; then $(PY) -m src.e_answers; else echo "make e: not built yet (#22-#23)"; fi

pitch:             ## fill every {{placeholder}} in METHOD_NOTE + docs/pitch from results → out/pitch/
	$(PY) -m src.story_fill

app:               ## Streamlit app (stop it before `make all`: it holds the DuckDB lock)
	@if [ -f app/Home.py ]; then $(PY) -m streamlit run app/Home.py; else echo "make app: not built yet (#20)"; fi

all: load a c e pitch   ## every submission file + pitch values from the unzipped pack (~1 min)

test:
	$(PY) -m pytest -q
