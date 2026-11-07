"""Data catalog of the serve database: one card per table, plus a deterministic keyword search.

Run:  python -m src.r_catalog     (reads SERVE_DB, default out/serve.duckdb; writes out/v2/catalog.json)

* A card describes a table: kind, pack source file, description and column descriptions (from the
  pack's DATA_DICTIONARY.md), row count, year range and key columns.
* `catalog_search` ranks cards with BM25 over table name, description and columns. No LLM, no numbers
  computed from the data beyond counts and min/max years. Views (the daily weather) are not scanned.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import duckdb

from src.db import REPO_ROOT, env
from src.load import pack_dir, table_name

CATALOG_PATH = REPO_ROOT / "out" / "v2" / "catalog.json"
DERIVED = {"results", "lineage", "corrections"}
DERIVED_DESC = {
    "results": "Computed numbers (metric, scope, category, year, scenario, value, unit, method) "
               "with status draft/approved/published.",
    "lineage": "Source records and factors behind each result (result_id -> source_ref, contribution).",
    "corrections": "Audit log of data fixes: record_key, field, old and new value, reason, approval.",
}
STEM_RENAMES = {"weather_daily_1991_2060": "weather_daily"}
ID_EXTRA = {"record_key", "doc_no", "line_no"}
# English tags searched like the description, and query synonyms (Swedish Foodhills headers)
TAGS = {"raw_foodhills_odlingsdata_se": ["pea", "deliveries", "swedish farms", "harvest year", "foodhills",
                                         "SE_SKANE"]}
SYNONYMS = [["pea", "ärt", "ärter", "frysärt"], ["delivery", "deliveries", "levererad", "leverans"],
            ["harvest", "skörd", "skördeår"], ["crop", "gröda"], ["area", "areal"],
            ["farm", "grower", "odlare", "odlar"], ["irrigated", "bevattnad"], ["nitrogen", "kväve"],
            ["swedish", "sweden", "se", "foodhills"]]
STOP = {"a", "an", "and", "by", "for", "from", "how", "id", "in", "is", "of", "on", "per", "the", "to", "what",
        "which", "with", "each", "all"}


# ── data dictionary ───────────────────────────────────────────────────
def _table_for(path: str) -> str:
    p = Path(path)
    stem = p.parent.name if "*" in p.stem else p.stem
    return table_name(STEM_RENAMES.get(stem, stem))


def parse_dictionary(text: str) -> dict[str, dict]:
    """Table name -> {source_file, description, columns: {name: description}}."""
    out: dict[str, dict] = {}
    cur: dict | None = None
    for line in text.splitlines():
        head = re.match(r"^## `([^`]+)`", line)
        if head:
            cur = {"source_file": head.group(1), "description": "", "columns": {}}
            out[_table_for(head.group(1))] = cur
            continue
        if line.startswith("## "):
            cur = None  # "Other files": parsed below as a table of files
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if cur is not None and len(cells) >= 4 and cells[0].startswith("`"):
            cur["columns"][cells[0].strip("`")] = cells[-1]
        elif cur is None and len(cells) == 3 and cells[0].startswith("`"):
            folder = ""
            for tok in re.findall(r"`([^`]+)`", cells[0]):
                path = tok if "/" in tok else f"{folder}/{tok}"
                folder = str(Path(path).parent)
                out.setdefault(_table_for(path), {"source_file": path, "description": cells[2], "columns": {}})
        elif cur is not None and line.strip() and not cells and not line.startswith("Rows:") and not cur["description"]:
            cur["description"] = line.strip()
    return out


# ── cards ─────────────────────────────────────────────────────────────
def _kind(table: str) -> str:
    return table.split("_", 1)[0] if table.startswith(("raw_", "clean_")) else table


def _allowed(con: duckdb.DuckDBPyConnection) -> list[tuple[str, bool]]:
    rows = con.execute("SELECT table_name, table_type FROM information_schema.tables "
                       "WHERE table_schema = 'main' ORDER BY table_name").fetchall()
    return [(n, t == "VIEW") for n, t in rows if n.startswith(("raw_", "clean_")) or n in DERIVED]


def _years(con: duckdb.DuckDBPyConnection, table: str, cols: dict[str, str]) -> list[int] | None:
    ycols = [c for c in cols if c == "year"] or [c for c in cols if c.endswith(("_year", "år"))]
    if ycols:
        expr = f'TRY_CAST("{ycols[0]}" AS INTEGER)'
    else:
        dates = [c for c, t in cols.items() if c == "date" or c.endswith("_date") or t in ("DATE", "TIMESTAMP")]
        if not dates:
            return None
        expr = f'year(TRY_CAST("{dates[0]}" AS DATE))'
    lo, hi = con.execute(f'SELECT min({expr}), max({expr}) FROM "{table}"').fetchone()
    return None if lo is None else [int(lo), int(hi)]


def _clean_entry(table: str, dic: dict[str, dict]) -> dict:
    base = table.removeprefix("clean_")
    raw = next((k for k in sorted(dic) if k == base or k.startswith(base + "_")), None)
    entry = dic.get(raw, {}) if raw else {}
    desc = f"Cleaned raw_{raw or base}: approved corrections applied, `corrected_fields` lists what changed."
    return {"source_file": None, "description": f"{desc} {entry.get('description', '')}".strip(),
            "columns": entry.get("columns", {})}


def build_cards(con: duckdb.DuckDBPyConnection, dictionary_path: Path | str | None = None) -> list[dict]:
    path = Path(dictionary_path) if dictionary_path else pack_dir() / "docs" / "DATA_DICTIONARY.md"
    dic = parse_dictionary(path.read_text(encoding="utf-8")) if path.is_file() else {}
    cards = []
    for table, is_view in _allowed(con):
        kind = _kind(table)
        if kind == "raw":
            entry = dic.get(table.removeprefix("raw_"), {})
        elif kind == "clean":
            entry = _clean_entry(table, dic)
        else:
            entry = {"source_file": None, "description": DERIVED_DESC.get(table, ""), "columns": {}}
        cols = {r[0]: r[1] for r in con.execute(f'DESCRIBE "{table}"').fetchall()}
        cards.append({
            "table": table, "kind": kind, "source_file": entry.get("source_file"),
            "description": entry.get("description") or None,
            "columns": [{"name": c, "type": t, "description": entry.get("columns", {}).get(c)}
                        for c, t in cols.items()],
            "row_count": None if is_view else con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0],
            "years": None if is_view else _years(con, table, cols),
            "key_columns": [c for c in cols if c in ID_EXTRA or c.endswith("_id")],
            "tags": TAGS.get(table, []),
        })
    return cards


def write_catalog(cards: list[dict], path: Path | str | None = None) -> Path:
    path = Path(path) if path else CATALOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cards, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def serve_db() -> Path:
    p = Path(env("SERVE_DB", "out/serve.duckdb")).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def load_cards() -> list[dict]:
    if CATALOG_PATH.is_file():
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    with duckdb.connect(str(serve_db()), read_only=True) as con:
        return build_cards(con)


# ── search ────────────────────────────────────────────────────────────
def tokens(text: str | None) -> list[str]:
    out = []
    for t in re.findall(r"[^\W_]+", (text or "").lower()):
        if t in STOP:
            continue
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3]
        elif len(t) > 5 and t.endswith(("ed", "ing")):
            t = t[:-3] if t.endswith("ing") else t[:-2]
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t[:-1] if len(t) > 4 and t.endswith("y") else t)
    return out


def expand(toks: list[str]) -> list[str]:
    """Query tokens plus their synonyms (deduplicated, order kept)."""
    return list(dict.fromkeys(s for t in toks for s in _synonyms(t)))


def _synonyms(t: str) -> list[str]:
    """The token first, then its synonyms (sorted)."""
    groups = [set(tokens(" ".join(g))) for g in SYNONYMS]
    return [t] + sorted({s for g in groups if t in g for s in g} - {t})


def _doc(card: dict) -> dict[str, float]:
    tf: dict[str, float] = {}
    parts = [(card["table"], 3.0), (card.get("description"), 1.0), (" ".join(card.get("tags") or []), 1.0)]
    for c in card["columns"]:
        parts += [(c["name"], 2.0), (c.get("description"), 1.0)]
    for text, w in parts:
        for t in tokens(text):
            tf[t] = tf.get(t, 0.0) + w
    return tf


def catalog_search(query: str, k: int = 5, cards: list[dict] | None = None) -> dict:
    cards = cards if cards is not None else load_cards()
    docs = [_doc(c) for c in cards]
    n, avg = len(docs), (sum(sum(d.values()) for d in docs) / len(docs)) if docs else 1.0
    q = [_synonyms(t) for t in dict.fromkeys(tokens(query))]
    scored = []
    for card, d in zip(cards, docs):
        length = sum(d.values())

        def bm25(t: str) -> float:
            df = sum(1 for x in docs if t in x)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            return idf * d[t] * 2.2 / (d[t] + 1.2 * (0.25 + 0.75 * length / avg)) if t in d else 0.0

        # each query word scores its best match; a synonym counts half
        score = sum(max([bm25(g[0])] + [0.5 * bm25(s) for s in g[1:]]) for g in q)
        if score > 0:
            scored.append((-round(score, 6), card["table"], card))
    hits = [{"table": c["table"], "description": c.get("description"),
             "columns": [x["name"] for x in c["columns"]], "years": c.get("years"),
             "source_file": c.get("source_file"), "score": -s} for s, _, c in sorted(scored)[:k]]
    return {"query": query, "tables": hits}


def main() -> None:
    with duckdb.connect(str(serve_db()), read_only=True) as con:
        cards = build_cards(con)
    path = write_catalog(cards)
    print(f"{len(cards)} cards -> {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    for q in ("pea deliveries by farm", "energy per site per month", "farm yield history",
              "pea deliveries from Swedish farms"):
        hits = catalog_search(q, k=3, cards=cards)["tables"]
        print(f"{q!r}: " + ", ".join(f"{h['table']} ({h['score']:.2f})" for h in hits))


if __name__ == "__main__":
    main()
