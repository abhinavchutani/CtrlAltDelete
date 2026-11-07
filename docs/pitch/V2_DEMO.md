# v2 demo script, video cut, Microsoft mapping slide

Run it: see the README's "v2" section (`make snapshot v2`, then `make api` and `make web`). Check it before going on
stage with `make demo-check`, which walks every beat below through the real API (9/9 on 7 Nov).

**Every line we say comes from the app's own output** (the quoted lines are what `make demo-check` printed on 7 Nov).
All figures come from the organisers' **synthetic twin**, not Apetit's real data; the app's banner says so. € values
are bands, never exact.

## Live demo (≈3 minutes)

| # | Do | Say (from the app's output) |
|---|---|---|
| 1 | The map opens on 2026. | "2026 on the twin: Swedish pea down 8 %, Finnish pea up 22 %. The drought shows in the weather layer over Skåne." |
| 2 | Say or type: *"How did pea deliveries from Swedish farms in 2026 compare with 2021?"* Then: *"Make that a report."* | "The answer comes with its table and evidence chips, from read-only SQL. The report downloads as Excel, with a Sources sheet." |
| 3 | Press play: current plan, SSP2-4.5, to 2040. Click the first critical dot. | "8 alerts, 5 of them critical. The first is flowering drought in Swedish pea in 2026, €250k–1M at risk, and the suggested lever is the region split." |
| 4 | Say: *"What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?"* Confirm the chips. | "It heard two levers and shows them before running. The run takes about 2 seconds. € at risk drops to €100–250k a year, better than the current plan." |
| 5 | Open the "better option" card. | "The model searched about 10 combinations on this weather path. This one saves less than €50k more, and it says why." |
| 6 | Switch to SSP5-8.5, 2060, and open the pathways. Add *"a heat-tolerant pea from 2030"*. | "On this weather path the 1-in-4 bad-year threshold isn't crossed before 2060, so there's no deadline yet. Here's what to watch: the signposts. The heat-tolerant pea is an assumption, not data, so confidence drops to low." |
| 7 | Open the hedge frontier (SSP2-4.5, then SSP5-8.5). | "Today's split, 30 % Finland, is already the most robust on this ensemble. Under SSP5-8.5, moving 5 points more to Finland cuts the 1-in-10-year loss by 3 %, still in the same band." |
| 8 | Open the decision board, approve one row with your name and a reason. | "One row per critical risk: the action from our adaptation knowledge base, the owner, and the evidence. Nothing is decided until a person signs it. The approval goes into an append-only log." |

**Don't say:**
- "decide by 2029", or any decide-by year: none exists on this data (human decision, 7 Nov);
- "the model predicted 2026";
- any € figure that isn't a band;
- that the knowledge-base options are agronomist-approved: they are marked "not yet reviewed".

**If something fails on stage:** restart with `API_MOCK=1 make api` (the committed fixtures) and say the numbers are
fixtures.

## Video cut (< 2 min; beats 1, 3, 4, 6, 8)

| Time | Shot |
|---|---|
| 0:00–0:15 | Beat 1: the 2026 map, Swedish pea red. Text: "Synthetic twin of Apetit." |
| 0:15–0:40 | Beat 3: play to 2040, dots appear; click the critical one. |
| 0:40–1:05 | Beat 4: the spoken what-if → chips → the map and meters update. |
| 1:05–1:30 | Beat 6: SSP5-8.5 pathways and signposts; the heat-tolerant pea turns confidence to low. |
| 1:30–1:50 | Beat 8: a human approves one board row with their name. |
| 1:50–2:00 | "Every number computed, every decision signed." |

## Microsoft mapping (slide text)

**Title:** The same pieces on Apetit's Microsoft stack

| v2 piece | Our build | Apetit stack |
|---|---|---|
| Data | `serve.duckdb` + catalog cards | Fabric Lakehouse + its semantic model |
| Retrieval tools | read-only SQL, docs search, Excel reports | Copilot Studio or Azure AI Foundry agent calling the same tools; Azure AI Search for docs |
| Prediction engine | Python yield model, scenario presets | Azure Machine Learning endpoint |
| API | FastAPI | Azure Functions or Container Apps |
| App | React (map, timeline, ask, board) | Static Web App, or embedded in Teams / Power BI |
| Voice | browser Web Speech API | Azure AI Speech |
| Approval log | `out/v2/decisions.jsonl` | a Lakehouse table + Power Automate approval |
| Paper diaries (future) | — | Azure Document Intelligence → the v1 review queue |

**Speaker line:** "Nothing here is tied to our laptop. Each piece has a direct Microsoft equivalent, and the rule
stays the same: deterministic code computes every number, and a person signs every decision."
