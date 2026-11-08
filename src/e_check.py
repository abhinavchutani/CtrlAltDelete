"""The copilot's number post-check: every number in an answer must equal a number a tool returned.

A number "equals" a tool number if it is the tool number rounded to the decimals the answer shows
(6,400 or 6,399.9 both match 6399.94). Exempt: numbers inside `code spans`, anything after the
evidence marker, numbers echoed from the question, and small integers (≤ 12) **only when they label
something** ("Scope 1", "Scope 1+2", "category 4", "step 2", a "1." list marker). A bare small quantity
("7 t", "10 %") must match a tool value like any other number.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

EVIDENCE_MARK = "**Evidence**"
_NUM = re.compile(r"(?<![\w.\-/:])(\d{1,3}(?:[,   ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w])")

_SCALED = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?(?:k|M|bn)\b")   # a figure written with a k / M / bn suffix


LABELS = {"scope", "scopes", "category", "categories", "cat", "step", "steps", "phase", "tier", "page",
          "section", "§", "option", "options", "action", "actions", "part", "level", "row", "rows",
          "version", "v", "question", "lever", "sdg", "goal", "principle", "article", "annex", "chapter"}
_LABEL_BEFORE = re.compile(r"([A-Za-z§]+)\s*(?:\d+\s*(?:[+,/&–-]|and|or)\s*)*$")


def _is_label(text: str, start: int) -> bool:
    """True if the number at `start` labels something rather than quantifying it."""
    before = text[max(0, start - 40):start]
    line_start = text.rfind("\n", 0, start) + 1
    if not text[line_start:start].strip() and re.match(r"\d+[.)]\s", text[start:start + 4]):
        return True  # numbered list marker
    m = _LABEL_BEFORE.search(before)
    return bool(m and m.group(1).lower() in LABELS)


def _parse(tok: str) -> tuple[float, int]:
    clean = re.sub(r"[,   ]", "", tok)
    decimals = len(clean.split(".")[1]) if "." in clean else 0
    return float(clean), decimals


def _prose(text: str) -> str:
    return re.sub(r"`[^`]*`", " ", text.split(EVIDENCE_MARK)[0])


def numbers_in(text: str) -> list[tuple[str, float, int]]:
    """(token, value, shown decimals) for every number in prose (code spans and evidence excluded)."""
    return [(m.group(1), *_parse(m.group(1))) for m in _NUM.finditer(_prose(text))]


def tool_numbers(obj: Any) -> set[float]:
    """Every number in a tool result: numeric values, and numbers written inside returned text."""
    out: set[float] = set()
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        out |= {v for _, v, _ in numbers_in(obj)}
        out |= {float(m.group(1)) for m in _SCALED.finditer(obj)}   # "€250k–1M" → 250, 1
    elif isinstance(obj, dict):
        for v in obj.values():
            out |= tool_numbers(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            out |= tool_numbers(v)
    return out


def _matches(value: float, decimals: int, allowed: Iterable[float]) -> bool:
    half = 0.5 * 10 ** -decimals
    return any(abs(abs(a) - value) <= half + 1e-9 * max(1.0, abs(a)) for a in allowed)


def unsupported_numbers(answer: str, tool_results: list[Any], question: str = "") -> list[str]:
    """Numbers in the answer that no tool returned. Empty list = the answer passes."""
    allowed = tool_numbers(tool_results) | {v for _, v, _ in numbers_in(question)}
    prose, bad = _prose(answer), []
    for m in _NUM.finditer(prose):
        tok = m.group(1)
        value, dec = _parse(tok)
        if dec == 0 and value <= 12 and _is_label(prose, m.start(1)):
            continue
        if not _matches(value, dec, allowed):
            bad.append(tok)
    return bad
