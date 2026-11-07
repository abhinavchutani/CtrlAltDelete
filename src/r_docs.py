"""Retrieval layer (v2): document search (task #86, V2-9).

    from src.r_docs import search_docs
    search_docs("guarantee of origin vintage rule")

Extends v1's `e_tools.search_frameworks` (framework digest, source registry, pack docs) with:
* the repo's METHOD_NOTE.md and REASONING_LOG.md (our stated rules R01–R34, one passage per table row);
* one passage per data-quality rule from the `issues` table: what it flags, an example explanation, and how
  many records it hit (from the frozen snapshot; read-only).
Same BM25 scoring and tokeniser as v1 (imported, not copied), so results are deterministic.
"""
from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

import duckdb

from src import e_tools as T
from src.db import REPO_ROOT

REPO_DOCS = ("METHOD_NOTE.md", "REASONING_LOG.md")
# Abbreviation ↔ full-term pairs from the pack's glossary, so "GoO" and "guarantee of origin" find the same passages.
EXPANSIONS = (
    (r"guarantees? of origin|\bgoos?\b", "goo guarantee origin vintage registry"),
    (r"\bpeat\b|organic soils?", "peat organic soil"),
    (r"ammonia|\br717\b", "ammonia r717 gwp"),
    (r"\bl27\b|better measurement", "l27 measurement lever reduction"),
    (r"credit notes?|movement 122", "credit note movement 122"),
    (r"\bpcfs?\b|product carbon footprint", "pcf supplier reference period"),
    (r"foodhills|grain trade|divest", "foodhills grain trade divested boundary base year recalculation"),
)
# Where our stated rules live: preferred when the question asks for a rule.
RULE_FILES = ("REASONING_LOG.md", "METHODOLOGY.md", "ASSUMPTIONS_AND_LIMITATIONS.md", "METHOD_NOTE.md")


def expand(query: str) -> str:
    """The query plus the glossary terms its abbreviations stand for (deterministic)."""
    import re
    extra = [terms for pat, terms in EXPANSIONS if re.search(pat, query, re.I)]
    return " ".join([query, *extra])


def _table_rows(file: str, text: str) -> list[T.Passage]:
    """Markdown table rows as their own passages (REASONING_LOG is one rule per row)."""
    out, section = [], "top"
    for line in text.splitlines():
        if line.startswith("#"):
            section = line.lstrip("#").strip()
        elif line.startswith("|") and not set(line.replace("|", "").strip()) <= set("-: "):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0].lower() not in {"id", "criterion", ""}:
                out.append(T.Passage(file, f"{section} · {cells[0]}", " | ".join(cells)))
    return out


def repo_passages(root: Path = REPO_ROOT) -> list[T.Passage]:
    out: list[T.Passage] = []
    for name in REPO_DOCS:
        p = root / name
        if p.exists():
            text = p.read_text()
            out += [x for x in T._split_markdown(name, text) if not x.text.lstrip().startswith("|")]
            out += _table_rows(name, text)
    return out


def rule_passages(con: duckdb.DuckDBPyConnection | None) -> list[T.Passage]:
    """One passage per detector rule: issue type, status, count and one example explanation."""
    if con is None:
        return []
    try:
        rows = con.execute("""SELECT rule_id, issue_type, status, count(*) AS n, min(explanation) AS example
                              FROM issues GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""").fetchall()
    except duckdb.Error:
        return []
    return [T.Passage("issues", f"rule {r}",
                      f"Data-quality rule {r} flags {t.replace('_', ' ')} ({s}): {n} records. Example: {ex}")
            for r, t, s, n, ex in rows]


@lru_cache(maxsize=2)
def _index(key: str, extra: tuple[T.Passage, ...]) -> tuple[list[T.Passage], list[Counter], dict[str, float], float]:
    base, *_ = T._index(key)
    passages = list(base) + list(extra)
    toks = [Counter(T._tokens(p.section + " " + p.text)) for p in passages]
    n = len(toks) or 1
    df = Counter(t for c in toks for t in c)
    idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
    avg = sum(sum(c.values()) for c in toks) / n
    return passages, toks, idf, avg


def search_docs(query: str, k: int = 4, con: duckdb.DuckDBPyConnection | None = None,
                root: Path | None = None, prefer_rules: bool = False) -> dict:
    """Top-k passages by BM25 over the pack docs + our method note, reasoning log and detector rules.
    `prefer_rules` boosts the files where our stated rules live (REASONING_LOG, METHODOLOGY, ASSUMPTIONS)."""
    extra = tuple(repo_passages() + rule_passages(con))
    passages, toks, idf, avg = _index(str(root or T.pack_dir()), extra)
    q = set(T._tokens(expand(query)))
    scored = []
    for p, c in zip(passages, toks):
        length = sum(c.values()) or 1
        s = sum(idf.get(t, 0) * c[t] * 2.2 / (c[t] + 1.2 * (0.25 + 0.75 * length / avg)) for t in q if t in c)
        if "framework_digest" in p.file:
            s *= 1.3
        if prefer_rules and any(p.file.endswith(f) for f in RULE_FILES):
            s *= 1.6
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda x: (-x[0], x[1].file, x[1].section))
    return {"query": query, "passages": [{"file": p.file, "section": p.section, "text": p.text, "score": round(s, 3)}
                                         for s, p in scored[:k]]}


if __name__ == "__main__":
    import json
    import sys
    from src.r_sql import connect
    print(json.dumps(search_docs(" ".join(sys.argv[1:]) or "guarantee of origin rule", con=connect()), indent=1)[:3000])
