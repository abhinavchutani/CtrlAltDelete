"""The copilot's number post-check: every number in an answer must equal a number a tool returned.

A number "equals" a tool number if it is the tool number rounded to the decimals the answer shows
(6,400 or 6,399.9 both match 6399.94). Small integers (≤ 12: scopes, categories, steps, months),
numbers inside `code spans`, and anything after the evidence marker are exempt. Numbers that appear
in the question itself are allowed (they can be echoed).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

EVIDENCE_MARK = "**Evidence**"
_NUM = re.compile(r"(?<![\w.\-/:])(\d{1,3}(?:[,   ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w])")


def _parse(tok: str) -> tuple[float, int]:
    clean = re.sub(r"[,   ]", "", tok)
    decimals = len(clean.split(".")[1]) if "." in clean else 0
    return float(clean), decimals


def numbers_in(text: str) -> list[tuple[str, float, int]]:
    """(token, value, shown decimals) for every number in prose (code spans and evidence excluded)."""
    prose = text.split(EVIDENCE_MARK)[0]
    prose = re.sub(r"`[^`]*`", " ", prose)
    return [(m.group(1), *_parse(m.group(1))) for m in _NUM.finditer(prose)]


def tool_numbers(obj: Any) -> set[float]:
    """Every number in a tool result: numeric values, and numbers written inside returned text."""
    out: set[float] = set()
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        out |= {v for _, v, _ in numbers_in(obj)}
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
    bad = []
    for tok, value, dec in numbers_in(answer):
        if dec == 0 and value <= 12:
            continue
        if not _matches(value, dec, allowed):
            bad.append(tok)
    return bad
