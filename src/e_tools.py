"""Copilot tools (Track E). The only places an answer's facts may come from.

* query_results(...)     parameterised SQL over `results` + `lineage`; optional deterministic sum.
                         Track A naming (#44): summary rows metric='tco2e', scope in
                         scope1|scope2_location|scope2_market|scope3|total|memo, category 'scopeN_total'
                         (scope='total') or 'catNN_<name>'; line items metric='tco2e_line'.
* search_frameworks(q)   keyword (BM25) retrieval over the pack's framework digest, source registry
                         and docs/; returns passages with file and section.

Both return plain dicts (JSON-serialisable) so they can be handed to an LLM as tool results.
"""
from __future__ import annotations

import csv
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import duckdb

from src import lineage as L
from src.db import REPO_ROOT, env

DEFAULT_PACK = "data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026"
PENDING = "pending expert approval"


# ── query_results ─────────────────────────────────────────────────────
def query_results(con: duckdb.DuckDBPyConnection, *, metric: str | None = None, scope: str | None = None,
                  category: str | None = None, year: int | None = None, scenario: str | None = None,
                  category_prefix: str | None = None, text: str | None = None, aggregate: str | None = None,
                  include_drafts: bool | None = None,
                  limit: int = 25) -> dict:
    """Rows of `results` matching every given filter, each with its lineage.

    Published and approved rows always count; drafts only with include_drafts (default: dev mode),
    and they are flagged. aggregate='sum' adds a code-computed total over the matched rows.
    """
    if include_drafts is None:
        include_drafts = L.dev_mode()
    where, params = ["status IN ('published','approved'" + (",'draft')" if include_drafts else ")")], []
    for col, val in (("metric", metric), ("scope", scope), ("category", category), ("year", year),
                     ("scenario", scenario)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(val)
    if category_prefix:
        where.append("category LIKE ?")
        params.append(category_prefix.replace("%", "") + "%")
    if text:
        where.append("(lower(result_id) LIKE ? OR lower(coalesce(category,'')) LIKE ?)")
        params += [f"%{text.lower()}%"] * 2
    rows = con.execute(f"SELECT result_id, metric, scope, category, year, scenario, value, unit, method, status "
                       f"FROM results WHERE {' AND '.join(where)} ORDER BY result_id LIMIT ?",
                       params + [limit]).df().to_dict(orient="records")
    for r in rows:
        r["lineage"] = con.execute("SELECT source_kind, source_ref, contribution FROM lineage WHERE result_id = ? "
                                   "ORDER BY source_kind, source_ref LIMIT 8", [r["result_id"]]).df().to_dict(orient="records")
        if r["status"] == "draft":
            r["badge"] = PENDING
    out: dict = {"filters": {k: v for k, v in dict(metric=metric, scope=scope, category=category, year=year,
                                                     scenario=scenario, category_prefix=category_prefix, text=text).items() if v is not None},
                 "n_rows": len(rows), "rows": rows}
    if aggregate == "sum" and rows:
        units = {r["unit"] for r in rows}
        if len(units) == 1:
            out["sum"] = round(sum(r["value"] for r in rows), 6)
            out["sum_unit"] = units.pop()
    return out


# ── search_frameworks ─────────────────────────────────────────────────
@dataclass(frozen=True)
class Passage:
    file: str
    section: str
    text: str


def pack_dir() -> Path:
    p = Path(env("DATA_DIR", DEFAULT_PACK)).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def _split_markdown(file: str, text: str, max_chars: int = 900) -> list[Passage]:
    out, section, buf = [], "top", []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            # one passage per paragraph or top-level bullet (the digest is one rule per bullet)
            for para in re.split(r"\n\s*\n|\n(?=[*-] )", body):
                para = para.strip()
                while para:
                    out.append(Passage(file, section, para[:max_chars]))
                    para = para[max_chars:]
        buf.clear()

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            section = line.lstrip("#").strip()
        else:
            buf.append(line)
    flush()
    return out


@lru_cache(maxsize=2)
def _index(root: str) -> tuple[list[Passage], list[Counter], dict[str, float], float]:
    base = Path(root)
    passages: list[Passage] = []
    fw = base / "data" / "07_frameworks"
    if (fw / "framework_digest.md").exists():
        passages += _split_markdown("data/07_frameworks/framework_digest.md", (fw / "framework_digest.md").read_text())
    if (fw / "source_registry.csv").exists():
        with open(fw / "source_registry.csv", newline="") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                passages.append(Passage("data/07_frameworks/source_registry.csv", f"row {i}",
                                        f"{r.get('source')}: used for {r.get('used_for')} ({r.get('url')})"))
    for md in sorted((base / "docs").glob("*.md")):
        passages += _split_markdown(f"docs/{md.name}", md.read_text())
    toks = [Counter(_tokens(p.section + " " + p.text)) for p in passages]
    n = len(toks) or 1
    df = Counter(t for c in toks for t in c)
    idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
    avg = sum(sum(c.values()) for c in toks) / n
    return passages, toks, idf, avg


_STOP = set("the a an of and or to in for on is are was were what which how does do by with as at be it its this that "
            "from under why can there their any".split())


def _tokens(s: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", s.lower())
    return [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words if w not in _STOP]


def search_frameworks(query: str, k: int = 4, root: Path | None = None) -> dict:
    """Top-k passages by BM25; the framework digest gets a small boost (it is the primary source)."""
    passages, toks, idf, avg = _index(str(root or pack_dir()))
    q = set(_tokens(query))
    scored = []
    for p, c in zip(passages, toks):
        length = sum(c.values()) or 1
        s = sum(idf.get(t, 0) * c[t] * 2.2 / (c[t] + 1.2 * (0.25 + 0.75 * length / avg)) for t in q if t in c)
        if "framework_digest" in p.file:
            s *= 1.3
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda x: (-x[0], x[1].file, x[1].section))
    return {"query": query, "passages": [{"file": p.file, "section": p.section, "text": p.text, "score": round(s, 3)}
                                         for s, p in scored[:k]]}
