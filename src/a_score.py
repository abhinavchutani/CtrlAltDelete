"""A1 scoring against the public 2023–24 dev labels (our re-implementation of the pack formula).

score = 100 × F1 × (0.75 + 0.25 × type_accuracy), matching on record_key.
Use `restrict_tables` to score one detector family on just the tables it covers.
Agents can't run the pack's own scorer (auto mode blocks executing pack code); humans should
cross-check with `python -m ccn_tools` (docs/BASELINES.md).
"""
from __future__ import annotations

import duckdb
import pandas as pd


def dev_labels(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute('SELECT "table" AS table_name, record_key, issue_type, year '
                       "FROM task_dev_A1_dev_issue_labels_2023_2024").df()


def score_a1(pred: pd.DataFrame, labels: pd.DataFrame, years=(2023, 2024),
             restrict_tables: list[str] | None = None) -> dict:
    lab = labels[labels.year.isin(years)]
    p = pred[pred.year.isin(years)] if "year" in pred else pred
    if restrict_tables:
        lab = lab[lab.table_name.isin(restrict_tables)]
        p = p[p.table_name.isin(restrict_tables)]
    # one prediction per record: keep the most confident
    p = p.sort_values("confidence", ascending=False).drop_duplicates("record_key")
    lab_types = lab.groupby("record_key").issue_type.agg(set)
    hit = p[p.record_key.isin(lab_types.index)]
    tp, n_pred, n_lab = len(hit), len(p), len(lab_types)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_lab if n_lab else 0.0
    f1 = 2 * precision * recall / (precision + recall) if tp else 0.0
    type_acc = (hit.apply(lambda r: r.issue_type in lab_types[r.record_key], axis=1).mean() if tp else 0.0)
    return {"score": round(100 * f1 * (0.75 + 0.25 * type_acc), 2), "f1": round(f1, 4),
            "precision": round(precision, 4), "recall": round(recall, 4), "type_accuracy": round(type_acc, 4),
            "tp": tp, "predicted": n_pred, "labels": n_lab}
