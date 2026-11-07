"""E answers CSV (task #23): every question in tasks/E_questions.csv through the same copilot.

Run:  python -m src.e_answers        (`make e`; needs the results DB from `make a` / `make c`)

* Template order and ids from tasks/templates/E_answers_submission.csv.
* Numeric questions: `answer` = the tool-returned value (code-computed; never model text), or empty with
  "not in the data: …" in `evidence` when the copilot can't ground it.
* Rubric questions: `answer` = the copilot's prose (pack passages in offline mode), `evidence` = file § section.
* A blocked reply (number check failed) is written as unanswered, never as its text.
Deterministic: the stub is rule-based, and LLM calls are cached by input hash (src/e_llm.py).
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

from src import e_agent, e_check, e_llm
from src.db import REPO_ROOT, connect
from src.e_tools import pack_dir

OUT = REPO_ROOT / "out" / "E_answers_submission.csv"


def _prose(markdown: str) -> str:
    """The answer text without the code-appended evidence block or badge, flattened to one line."""
    body = markdown.split(e_check.EVIDENCE_MARK)[0]
    body = re.sub(r"\n+🟠 \*.*?\*", "", body)
    body = re.sub(r"(^|\n)> ", r"\1", body)          # blockquote markers only, not '<scope> '
    return re.sub(r"\s+", " ", body).strip()


def answer_row(con: duckdb.DuckDBPyConnection, q: pd.Series) -> dict:
    a = e_agent.answer(q["question"], kind=q["kind"], con=con)
    ev = "; ".join(a.evidence)
    if a.pending:
        ev = f"{ev} (draft results, pending expert approval)"
    if a.blocked or not a.evidence:
        return {"question_id": q["question_id"], "answer": "", "evidence": f"not in the data: {_prose(a.markdown)}"}
    if q["kind"] == "numeric":
        return {"question_id": q["question_id"], "answer": "" if a.value is None else round(float(a.value), 4),
                "evidence": ev}
    return {"question_id": q["question_id"], "answer": _prose(a.markdown), "evidence": ev}


def build(con: duckdb.DuckDBPyConnection, root: Path | None = None) -> pd.DataFrame:
    root = root or pack_dir()
    qs = pd.read_csv(root / "tasks" / "E_questions.csv")
    order = pd.read_csv(root / "tasks" / "templates" / "E_answers_submission.csv")["question_id"]
    rows = {r["question_id"]: answer_row(con, r) for _, r in qs.iterrows()}
    out = pd.DataFrame([rows.get(i, {"question_id": i, "answer": "", "evidence": "question not found"}) for i in order])
    return out[["question_id", "answer", "evidence"]]


def dev_check(out: pd.DataFrame, root: Path | None = None) -> pd.DataFrame:
    """E90–E92 (public dev answers) vs our answers, with the pack's relative tolerances."""
    dev = pd.read_csv((root or pack_dir()) / "tasks" / "dev" / "E_dev_answers.csv")
    m = dev.merge(out, on="question_id", suffixes=("_dev", ""))
    m["ours"] = pd.to_numeric(m["answer"], errors="coerce")
    m["rel_err"] = (m["ours"] - m["answer_dev"]).abs() / m["answer_dev"].abs()
    m["ok"] = m["rel_err"] <= m["tolerance_rel"]
    return m[["question_id", "answer_dev", "ours", "rel_err", "tolerance_rel", "ok"]]


def main() -> None:
    con = connect(read_only=True)
    out = build(con)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    answered = int((out["answer"].astype(str) != "").sum())
    print(f"E: {answered}/{len(out)} answered → {OUT.relative_to(REPO_ROOT)} (mode: {e_llm.model_name()})")
    print(dev_check(out).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
