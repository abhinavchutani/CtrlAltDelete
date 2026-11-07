"""Prediction layer (v2): text → intent → ScenarioSpec (task #90, V2-8). POST /api/intent.

    parse("What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?")
    → {"door": "simulate", "spec": {...levers...}, "heard": ["irrigate the driest pea fields", "pea split: 70 % Finland"], ...}

* door: "simulate" when the text names a lever, a climate path or what-if wording; otherwise "ask" (retrieval).
* Offline (no key, the demo default): keyword + number rules. With an LLM key (src/e_llm, cached, temperature 0)
  the model only fills the ScenarioSpec form; the result goes through the same p_spec.validate.
* It never invents a lever or fixes a value silently: unknown asks and out-of-range numbers land in `problems`
  (shown to the user as chips), e.g. "a 95/5 split" → problem, not a clamped 0.9.
* `base` (optional) is the spec on screen, so "add a heat-tolerant pea from 2030" extends it.
"""
from __future__ import annotations

import json
import re

from src import p_spec as S

CLIMATE_WORDS = [  # (pattern, climate, chip)
    (r"ssp\s*5[-‐–]?\s*8\.?5|ssp585|worst[- ]case|high[- ]emission|hot(?:test)? future|business as usual",
     "ssp585", "climate: high emissions (SSP5-8.5)"),
    (r"ssp\s*2[-‐–]?\s*4\.?5|ssp245|middle(?:[- ]of[- ]the[- ]road| path)?|medium|moderate",
     "ssp245", "climate: middle path (SSP2-4.5)"),
    (r"ssp\s*1[-‐–]?\s*2\.?6|ssp126|low[- ]emission|paris|best[- ]case|optimistic", "ssp126", "climate: low emissions (SSP1-2.6)"),
]
WHAT_IF = r"\b(what if|what happens|if we|suppose|imagine|simulate|scenario|switch to|try|let'?s|could we|should we)\b"
CROP_WORDS = {"pea": r"peas?|ärt", "potato": r"potato(?:es)?", "carrot": r"carrots?", "spinach": r"spinach",
              "turnip_rape": r"turnip[ _-]?rape|rapeseed|oilseed rape", "wheat": r"wheat", "barley": r"barley", "oats": r"oats?"}
REGION_WORDS = {"FI_SW": r"finland|finnish|\bfi\b", "SE_SKANE": r"sweden|swedish|sk[aå]ne|\bse\b"}
UNKNOWN_LEVERS = [  # things people ask for that the engine cannot re-run → problems (RISK_MITIGATION §9)
    (r"cover crop|catch crop", "catch crops are not an engine lever yet"),
    (r"insurance|hedg(?:e|ing) contract|weather index", "weather-index contracts are not simulated"),
    (r"frozen stock|stock ?pile|buffer stock", "frozen-stock buffers are not simulated"),
    (r"price|premium|contract price", "price changes are not a lever; € uses 2025 contract prices"),
    (r"new region|poland|baltic|estonia|denmark", "only FI_SW and SE_SKANE can be sourced in the engine"),
]


def _crop(text: str, default: str | None = None) -> str | None:
    for crop, pat in CROP_WORDS.items():
        if re.search(rf"\b(?:{pat})\b", text):
            return crop
    return default


def _climate(t: str) -> tuple[str | None, str | None]:
    for pat, climate, chip in CLIMATE_WORDS:
        if re.search(pat, t):
            return climate, chip
    return None, None


def _horizon(t: str) -> tuple[int | None, str | None]:
    m = re.search(r"\b(?:to|until|till|by|through|horizon|out to)\s+(20\d\d)\b", t) or re.search(r"\b(2031|2040|2050|2060)\b", t)
    if not m:
        return None, None
    y = int(m.group(1))
    h = next((h for h in S.HORIZONS if h >= y), None)
    return (h, f"horizon: to {h}") if h else (None, f"horizon {y} is past 2060")


def _today_fi_share() -> float | None:
    """Today's Finland share of contracted pea volume, from the current-plan cube (if built)."""
    try:
        import pandas as pd
        from src.db import REPO_ROOT
        c = pd.read_parquet(REPO_ROOT / "out" / "v2" / "cube" / "current_plan_ssp245.parquet")
        v = c[c.crop == "pea"].groupby("region").contracted_t.first()
        return float(v["FI_SW"] / v.sum())
    except Exception:  # noqa: BLE001 — optional; relative moves become a problem instead
        return None


def _split(t: str, problems: list[str]) -> dict | None:
    m = re.search(r"\b(\d{1,2})\s*(?:/|–|-|:|to)\s*(\d{1,2})\b", t)
    if m and re.search(r"split|finland|sweden|fi\b|se\b|sourc", t) and int(m.group(1)) + int(m.group(2)) == 100:
        a, b = int(m.group(1)), int(m.group(2))
        fi = a if t.find("finland", 0) <= t.find("sweden", 0) or "sweden" not in t or "finland" not in t else b
        if re.search(r"sweden\W+finland|se\W+fi\b", t):
            fi = b
        return {"type": "region_split", "crop": "pea", "fi_share": fi / 100}
    m = re.search(r"(\d{1,3})\s*%?\s*(?:of (?:the )?peas? )?(?:in|from|to)?\s*finland", t)
    if m and re.search(r"split|sourc|move|shift|finland share", t) and not re.search(r"\bpp\b|points?", t):
        return {"type": "region_split", "crop": "pea", "fi_share": int(m.group(1)) / 100}
    m = re.search(r"(?:move|shift)\s+(\d{1,2})\s*(?:pp|percentage points?|points?)\s*(?:of (?:the )?peas? )?(?:to|into)\s+(finland|sweden)", t)
    if m:
        now = _today_fi_share()
        if now is None:
            problems.append("a relative move needs today's split; say it as e.g. 'a 50/50 split'")
            return None
        d = int(m.group(1)) / 100 * (1 if m.group(2) == "finland" else -1)
        return {"type": "region_split", "crop": "pea", "fi_share": round(now + d, 2)}
    return None


def offline(text: str, base: dict | None = None) -> dict:
    t = text.lower().replace("’", "'")
    spec = dict(base or S.default_spec())
    spec["levers"] = list(spec.get("levers", []))
    heard, problems, levers = [], [], []

    climate, chip = _climate(t)
    if climate:
        spec["climate"] = climate
        heard.append(chip)
    horizon, hchip = _horizon(t)
    if horizon:
        spec["horizon_end"] = horizon
        heard.append(hchip)
    elif hchip:
        problems.append(hchip)

    if re.search(r"irrigat|watering|water the", t):
        crop = _crop(t, "pea")
        target = "all" if re.search(r"\ball\b|every", t) else "drought_exposed"
        levers.append({"type": "irrigate", "crop": crop, "target": target})
        heard.append(f"irrigate {'all' if target == 'all' else 'the driest'} {crop} fields")
    sp = _split(t, problems)
    if sp:
        levers.append(sp)
        heard.append(f"pea split: {round(100 * sp['fi_share'])} % Finland")
    if re.search(r"heat[- ]?toleran|drought[- ]?toleran|new variet|breed", t):
        y = re.search(r"from\s+(20\d\d)|in\s+(20\d\d)|by\s+(20\d\d)", t)
        cut = re.search(r"(\d{1,2})\s*%\s*(?:less|fewer|lower|cut|reduction)", t)
        lv = {"type": "heat_tolerant_variety", "crop": "pea"}
        if y:
            lv["from_year"] = int(next(g for g in y.groups() if g))
        if cut:
            lv["penalty_cut"] = int(cut.group(1)) / 100
        levers.append(lv)
        heard.append(f"heat-tolerant pea from {lv.get('from_year', 2030)} (assumption)")
    if re.search(r"(?:sow|plant)(?:ing)?\s+(?:\w+\s+)?earl|earl\w*\s+(?:sow|plant)", t):
        crop = _crop(t, "all")
        levers.append({"type": "earlier_sowing", "crop": crop})
        heard.append(f"earlier sowing ({crop})")
    m = re.search(r"(cut|reduce|grow|increase|expand|shrink|halve|double)\w*\s+(?:the\s+)?(?:\w+\s+){0,3}?area[^.]*?(?:by\s+)?(\d{1,3})?\s*%?", t) \
        or re.search(r"(\d{1,3})\s*%\s*(less|more|fewer)\s+(?:\w+\s+){0,2}?(?:area|hectares|fields)", t)
    if m and re.search(r"area|hectare|fields", t) and not re.search(r"irrigat", t[m.start():m.end()]):
        nums = [int(x) for x in re.findall(r"(\d{1,3})\s*%", t[m.start():]) if x]
        sign = -1 if re.search(r"cut|reduce|shrink|halve|less|fewer", m.group(0)) else 1
        pct = 50 if "halve" in m.group(0) else 100 if "double" in m.group(0) else (nums[0] if nums else None)
        crop = _crop(t, None)
        region = next((r for r, pat in REGION_WORDS.items() if re.search(pat, t)), None)
        if pct is None or crop is None or region is None:
            problems.append("crop area change needs a crop, a region and a % (e.g. 'cut Swedish pea area by 20 %')")
        else:
            levers.append({"type": "crop_area", "crop": crop, "region": region, "change_pct": sign * pct})
            heard.append(f"{crop} area in {region} {sign * pct:+d} %")
    for pat, why in UNKNOWN_LEVERS:
        if re.search(pat, t):
            problems.append(why)
    if re.search(r"current plan|no change|as (?:it|we) (?:is|are)|baseline|do nothing", t) and not levers:
        spec["levers"] = []
        heard.append("the current plan (no levers)")

    simulate = bool(levers or climate or horizon or re.search(WHAT_IF, t) or "current plan" in t)
    if not simulate:
        return {"door": "ask", "text": text, "spec": None, "heard": [], "problems": []}
    clean, p2 = S.validate({**spec, "levers": spec["levers"] + levers})
    if not clean["levers"] and not levers and not climate and not horizon and not re.search(r"current plan|baseline", t):
        problems.append("no lever recognised: try irrigation, a Finland/Sweden split, earlier sowing, "
                        "a heat-tolerant pea or a crop-area change")
    clean["label"] = "; ".join(h for h in heard if not h.startswith(("climate", "horizon"))) or None
    return {"door": "simulate", "text": text, "spec": clean, "heard": heard, "problems": problems + p2}


LLM_SYSTEM = ("You turn a planner's sentence into a JSON form for a crop-climate scenario. Output ONLY JSON: "
              '{"door": "simulate"|"ask", "climate": "ssp126"|"ssp245"|"ssp585"|null, "horizon_end": 2031|2040|2050|2060|null, '
              '"levers": [...], "unknown": ["things asked for that are not a lever"]}. Levers: '
              '{"type":"irrigate","crop":"pea"|"potato","target":"drought_exposed"|"all"}, '
              '{"type":"earlier_sowing","crop":"<crop>"|"all"}, {"type":"region_split","crop":"pea","fi_share":0.2-0.9}, '
              '{"type":"heat_tolerant_variety","crop":"pea","from_year":2027-2060,"penalty_cut":0-0.6}, '
              '{"type":"crop_area","crop":"<crop>","region":"FI_SW"|"SE_SKANE","change_pct":-50..50}. '
              "Never invent a lever or a number the sentence does not give; questions about the past are door 'ask'.")


def llm(text: str, base: dict | None = None) -> dict | None:
    from src import e_llm
    if not e_llm.available():
        return None
    try:
        msg = e_llm.chat([{"role": "system", "content": LLM_SYSTEM}, {"role": "user", "content": text}])
        form = json.loads(re.search(r"\{.*\}", msg.get("content", ""), re.S).group(0))
    except Exception:  # noqa: BLE001 — any LLM failure falls back to the offline rules
        return None
    if form.get("door") == "ask":
        return {"door": "ask", "text": text, "spec": None, "heard": [], "problems": []}
    spec = dict(base or S.default_spec())
    for k in ("climate", "horizon_end"):
        if form.get(k):
            spec[k] = form[k]
    clean, problems = S.validate({**spec, "levers": list(spec.get("levers", [])) + list(form.get("levers") or [])})
    heard = [f"climate: {clean['climate']}", f"horizon: to {clean['horizon_end']}"] + \
            [lv["type"].replace("_", " ") for lv in clean["levers"]]
    return {"door": "simulate", "text": text, "spec": clean, "heard": heard,
            "problems": problems + [f"not a lever: {u}" for u in form.get("unknown") or []]}


def parse(text: str, base: dict | None = None) -> dict:
    """IntentOut dict. LLM form-filling when a key is set, else (or on any failure) the offline rules."""
    return llm(text, base) or offline(text, base)


if __name__ == "__main__":
    import sys
    print(json.dumps(parse(" ".join(sys.argv[1:]) or "What if we irrigate the driest pea fields and move to a 70/30 "
                                                       "Finland–Sweden split?"), indent=1, ensure_ascii=False))
