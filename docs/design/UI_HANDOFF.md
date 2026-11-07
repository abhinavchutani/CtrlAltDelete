# UI handoff: "Field Radar" redesign (branch `ui/design`)

**Goal image:** [field_radar_goal.webp](field_radar_goal.webp). Dark satellite map, fields glowing green/amber/red,
glass panels: layers (top-left), parcel card (top-right), stats bar + timeline (bottom), icon rail (left).
**Plus:** a RAG assistant that docks beside the map, maximises, or collapses to a pill.
The radar reticle and sweep from the goal image are **removed for now** (human call, 2026-11-07).

## Run it
```
make snapshot && python -m src.p_presets && python -m src.p_weather      # once: out/serve.duckdb + out/v2
API_MOCK=0 ~/.navigator-venv/bin/python -m uvicorn api.main:app --port 8000
cd web && npm ci && npm run dev                                           # http://localhost:5173 (proxies /api)
```
`~/.navigator-venv` is a Python env outside iCloud (the repo's `.venv` was offloaded by iCloud on a full disk;
any env with `pip install -r requirements.txt` works). Open in Chrome for the mic. In the Claude desktop app the
two servers are `navigator-api` and `navigator-web` in `.claude/launch.json` (the repo-root copy is git-excluded).
After changing `api/geo.py`, restart the API: `geo.parcels()` is cached for the process.

## Done
Checked in the browser at 1440×900 and 1280×800, chat docked and collapsed. `npm run build` and `pytest -q` pass.

**Shell and map**
- `src/App.tsx`: rail | stage | assistant column (`chat-docked/max/collapsed`).
- `src/theme/tokens.css`: the dark glass theme; all colours and sizes live here.
- `src/features/map/basemap.ts`: Esri World Imagery, darkened (no key; `VITE_BASEMAP_STYLE` overrides).
- `MapView.tsx` + `layers/parcels.ts`: parcels as translucent fills with glowing edges; click → parcel card.
  The map opens on the densest Skåne cluster (13.33 E, 55.85 N, zoom 12.3).
- Layout follows the **stage** width, not the window (`.stage` is a CSS size container). Below 1240 px of map
  the timeline drops to its own row under the stats, and the drawer keeps clear of it.
- The synthetic-data banner sits top-right, above the parcel card column, so it never covers the brand.

**Colours (all from the API, `fieldradar/useFieldData.ts`)**
- Farm health = the farm's own `risk` class from `/api/cube/{id}/farms` (ok → green, watch → amber, bad → red).
  The UI used to recolour the raw % on its own scale, so a −8 % farm the API calls "ok" showed amber and the
  map disagreed with the "% farms ok" stat. Now the map, the stat and the legend share the API's class.
- € risk = the band for the **parcel's own 2025 crop** in its region (`SimResult.regions`). Only contract crops
  have a band (SW Finland: pea, carrot, potato, spinach, turnip rape; Skåne: pea). Barley, wheat, ley… show as an
  outline, never as pea's band.
- Drought / heat = the nearest weather cell (`/api/weather`).

**API: parcel crop.** `/api/geo/parcels` now carries `crop`: the crop declared for 2025, joined at read time
from `raw_parcel_crop_history_and_plan` in the snapshot (2025 mix, the same rule the predictions use). The
geometry cache in `out/v2/geo_parcels.json` is unchanged. The mock fixture and `fixtures_build.py` carry it too.
Tests: `test_with_crops_adds_the_2025_crop_or_none`, `test_real_parcels_carry_a_crop`.

**Panels**
- `LayerPanel.tsx`: scenario, year, "colour fields by" (one layer at a time) and a **legend** for that layer.
  The legend uses the API's class names and band labels; no thresholds are typed in the UI.
- `ParcelCard.tsx`: outline thumbnail, **crop**, farm, area, region, € band for that crop (or "not a contract
  crop"), level = the worse of the farm class and the € band, yield % vs 1991–2020, Watch.
- `StatsBar.tsx`: % farms ok, the worst € band this year with its region and crop, drought for the region in view,
  then play + timeline with alert dots. A year that isn't a tick shows its label under the cursor.
- `Sidebar.tsx` / `Drawer.tsx`: insights (meters, alerts, hedge, pathways) and the decision board. Meters now
  render as a label/value grid.
- `chat/ChatDock.tsx`: each message → `/api/intent`; ask → `/api/ask` answer + table + evidence + report;
  what-if → heard chips + "Run on the map".

**Alert pins (`map/layers/pins.ts`)**
- Each alert of the chosen year gets a pin on the **worst-hit parcel of its crop in its region** (the farm with
  the lowest yield change; ties → the larger parcel). Alerts on the same parcel share one pin, worst severity first.
- Click a pin → the alert card, map stays put. Pick an alert anywhere else (timeline dot, insights list) → the map
  centres on its pin once that year's farms load.

**Fixes**
- `ChatDock` crashed the whole app on load: `useEffect(() => el.scrollIntoView())` returned the call's value, and
  this Chromium returns a Promise from `scrollIntoView`, which React then called as cleanup. Braces fixed it.
- Region views are flat now (pitch 0) to match the top-down satellite look.

## Next (in order)
1. The answer table in the chat is too wide when the first column is a long id (`line_result_id`): show a short
   label or let `ResultTable` hide id columns in the chat bubble.
2. Pins only cover the chosen year. Consider showing next year's alerts faintly, or a "jump to next alert" button.
3. A smooth fly-to when the map recentres on a pin (deck.gl `FlyToInterpolator` with the controlled view state).
4. Mobile / narrow (< 760 px of map): the rules exist but have not been checked in the browser.
5. Rules that must stay: the synthetic-data banner always visible; € only as bands; no "decide by" years (human
   decision: 1-in-4 threshold, none crossed); numbers only from the API, never typed in the UI.

## Known open bugs (other lanes)
- `PathwaysGantt`: duplicate React keys (`A01-FI_SW-ssp245`, …) when one option has several rows.
- A decision board approval with a whitespace-only name → 500. row_id is positional (PR #114 comments).
- A knowledge item can be approved by its own contributor (PR #114 comments).
