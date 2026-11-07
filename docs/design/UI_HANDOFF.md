# UI handoff: "Field Radar" redesign (branch `ui/design`)

**Goal image:** [field_radar_goal.webp](field_radar_goal.webp). Dark satellite map, fields glowing green/amber/red,
radar reticle, glass panels: layers (top-left), parcel card (top-right), stats bar + timeline (bottom), icon rail (left).
**Plus:** a RAG assistant that docks beside the map, maximises, or collapses to a pill.

## Run it
```
make snapshot && python -m src.p_presets && python -m src.p_weather      # once: out/serve.duckdb + out/v2
API_MOCK=0 ~/.navigator-venv/bin/python -m uvicorn api.main:app --port 8000
cd web && npm ci && npm run dev                                           # http://localhost:5173 (proxies /api)
```
`~/.navigator-venv` is a Python env outside iCloud (the repo's `.venv` was offloaded by iCloud on a full disk;
any env with `pip install -r requirements.txt` works). Open in Chrome for the mic.

## Done (this commit; `tsc --noEmit` passes, NOT yet checked in the browser)
- `src/App.tsx`: new shell (rail | stage | assistant column; `chat-docked/max/collapsed` classes).
- `src/theme/tokens.css`: full dark "glass" theme. All colours and sizes live here.
- `src/features/map/basemap.ts`: Esri World Imagery satellite tiles, darkened (no key; `VITE_BASEMAP_STYLE` overrides).
- `src/features/map/MapView.tsx` + `layers/parcels.ts`: parcels as translucent fills + glowing edges; click → parcel card.
  The map opens on the densest Skåne cluster (13.33 E, 55.85 N, zoom 12.3; "Skåne" / "SW Finland" jump chips).
- `src/features/map/RadarOverlay.tsx`: rings + crosshair ticks + CSS conic sweep (decorative, pointer-events none).
- `src/features/fieldradar/useFieldData.ts`: **all colours come from the API**:
  - health = farm yield change (`/api/cube/{id}/farms`);
  - € risk = region pea band (SimResult.regions);
  - drought / heat = the nearest weather cell (`/api/weather`).
  - Stats: % farms ok, worst € band, drought level of the region in view.
- `fieldradar/LayerPanel.tsx`: scenario, year, "colour fields by" switches (one at a time). `ParcelCard.tsx`: outline thumb,
  € band, risk badge, yield %, Watch. `StatsBar.tsx`: 3 stats + play + timeline with alert dots.
  `Sidebar.tsx`: map / insights / decisions / assistant. `Drawer.tsx`: the old meters, alerts, hedge, pathways and board panels.
- `src/features/chat/ChatDock.tsx`: each message → `/api/intent`.
  - ask → `/api/ask` answer + table + evidence chips + report;
  - what-if → heard chips + "Run on the map" (`runSpec`).
  - Suggestions, mic, maximise / dock / minimise. Store: `colorBy, selectedParcel, watched, drawer, chatMode, chat` in `state/store.ts`.

## Next (in order)
1. Open http://localhost:5173 and fix what looks off: panel overlaps at 1280–1440 px, drawer vs layer panel, the chat
   column width, the satellite tile load. If the API isn't warm, panels show "Loading…".
2. Parcel crop isn't in `/api/geo/parcels`. Add `crop` (2025 declared) there in `api/geo.py`, then show it on the card
   and colour € risk by that crop instead of pea.
3. Map pins for alerts (mock-up markers): use alert region + the worst parcel of that farm; click → AlertPopup.
4. Legend (green/amber/red meaning per layer) under the layer switches.
5. Rules that must stay: the synthetic-data banner always visible; € only as bands; no "decide by" years (human decision:
   1-in-4 threshold, none crossed); numbers only from the API, never typed in the UI.

## Known open bugs (other lanes, see PR #114 comments)
- A decision board approval with a whitespace-only name → 500. row_id is positional.
- A knowledge item can be approved by its own contributor.
