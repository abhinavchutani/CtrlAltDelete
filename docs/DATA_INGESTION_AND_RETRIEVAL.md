# Data Ingestion, Organisation & Retrieval — Design Doc
*Apetit × SinceAI 2026 · Track E (copilot with audit trail) + evidence layer for Track C · draft 7 Nov 2026*

---

## 1. The pitch in one line

> **Drop in anything — an ERP export, a supplier file, a photo of a paper note, or just tell the bot what you know — and it lands tagged, linked, quality-checked and traceable. Every number can be clicked down to the receipt.**

### What the judges told us (7 Nov meeting)
- Pain point #1: data is **scattered** — ERP, many Excels, paper notes, people's heads. Processing it is "unnecessary work".
- There is **no API or connector** to plug into; Apetit is only starting to test Microsoft Copilot.
- They want basic reporting automated so the data can be **used for decisions**.
- "Good enough" beats perfect; usefulness, sound reasoning and traceability matter, auto-scores don't.

### Design principles
1. **Extract at ingest, not at question time.** Every input becomes structured facts with provenance. Retrieval runs over facts + documents, not raw chunks.
2. **Numbers are computed, never generated.** Numeric answers come from queries over facts; the LLM only phrases them.
3. **Everything is tagged, linked and traceable.** Same treatment for files, records and human knowledge.
4. **Nothing is published without a human.** Low-confidence extractions, corrections and new knowledge go through review.
5. **Show the pipeline is ready**, not that we have lots of data. Breadth of formats + measured accuracy > volume.

---

## 2. What we ingest (synthetic only)

### 2.1 Already in the package
| Real-world mess at Apetit | Package file(s) | Mess built in |
|---|---|---|
| ERP exports | `02_raw_feeds/erp_purchase_lines_2021_2025.csv` | Units (vessel lots in t, truck lots in kg), credit notes, currency errors, Finnish ERP texts |
| Apetit's own Excel | `00_apetit_original/` sample workbook | Unchanged partner file |
| Supplier documents | `02_raw_feeds/supplier_pcfs/SUPxxx_Mxxx_YYYY.json` | PCF unit errors, stale periods |
| Farmer forms | `03_farming/farm_survey_fi.csv`, `foodhills_odlingsdata_se.csv` | Swedish-language file, soil misreports, outliers |
| Operational logs | energy meters, fuel deliveries + stock changes, refrigerant log, waste transfer notes, water, wastewater | Meter spikes, missing months, wrong gas codes, decimal shifts |
| Certificates | `goo_cancellations.csv` vs `goo_registry_statement.csv` | Internal log vs authoritative registry |
| Travel & people data | travel bookings, commuting survey, headcount | Duplicates, mode mislabels |
| Logistics | shipments, frozen warehousing | Missing legs |
| Master data | sites, materials, suppliers, farms, parcels, catchments, emission factors | The join keys |
| Standards | `07_frameworks/framework_digest.md`, `source_registry.csv` | Text for document retrieval |

### 2.2 Generated messy formats (`tools/messify.py`)
Formats the package lacks are **rendered from known package rows**, so the ground truth is known and extraction accuracy can be measured.

| Format | Generated from | Mess added |
|---|---|---|
| PDF invoices | ERP purchase lines | Varied layouts, Finnish labels, VAT lines, totals |
| Photos of handwritten / paper notes | waste transfer notes, meter readings | Rotation, blur, shadows, handwriting font |
| Emails | meter readings, fuel deliveries | Free text ("Oct steam at Kantvik was 412 MWh, sorry for the delay") |
| Odd-layout Excel | energy, refrigerants | Merged headers, Finnish column names, totals rows, months as columns |
| Scanned forms | farm survey rows | Checkboxes, partial fills |

Output: `generated/` documents + `generated/ground_truth.csv` (document → expected fields). All labelled **synthetic** in UI and method note.

---

## 3. The key observation: the IDs do the linking

The package shares stable IDs across every file (see `docs/DATA_DICTIONARY.md`):

| ID | Example | Meaning |
|---|---|---|
| `site_id` | `S-SAK` | Group site (Säkylä plant) |
| `supplier_id` | `SUP073` | Supplier |
| `material_id` | `M110` | Material (ERP text partly Finnish) |
| `farm_id` | `F0001` / `S…` | Contract farm (F = Finland, S = Sweden) |
| `parcel_id` | `F0001-P01` | Field parcel |
| `catchment_id` | `CA28` | Catchment |
| `ef_id` | `EF-RAP-EE` | Emission factor |
| record keys | `erp:{doc_no}:{line_no}`, `energy:{site}:{YYYY-MM}:{carrier}` … | Record-level identity (from TASKS_AND_SCORING.md) |

**File names carry tags too:** `SUP073_M154_2025.json` → supplier SUP073, material M154, year 2025.

→ Most graph edges are **deterministic**. AI is only needed for the messy parts: document type detection, unseen layouts, Finnish/Swedish free text → IDs, units, handwriting, and tacit knowledge.

---

## 4. Tag taxonomy (faceted, controlled)

Tags are applied to **files, records and knowledge items** alike. Controlled vocabulary per facet — no free-form tags.

| Facet | Values (examples) | Assigned by |
|---|---|---|
| `entity` | `site:S-SAK`, `supplier:SUP073`, `material:M110`, `farm:F0001`, `parcel:F0001-P01`, `catchment:CA28`, `ef:EF-RAP-EE` | ID columns, file names, entity resolution |
| `time` | `year:2025`, `month:2025-10`, `season:2026` | Dates, file names |
| `domain` | energy, fuels, refrigerants, purchases, logistics, waste, water, travel, commuting, farming, climate, nature, certificates | Schema match |
| `ghg` | `scope:1`, `scope:2-lb`, `scope:2-mb`, `scope3:cat1` … `cat12`, `flag` | Mapping rules (e.g. inbound shipments → cat 4, outbound → cat 9) |
| `doc_type` | erp_export, meter_reading, supplier_pcf, survey, certificate, log, invoice, email, note_photo, knowledge | Classifier |
| `geo` | `FI`, `SE`, `FI_SW`, `SE_SKANE` | Registries |
| `quality` | `clean`, `flagged:<issue_type>`, `corrected`, `approved`, `pending_review` | Quality checks + reviewers |
| `framework` | ghg_protocol, sbti_flag, sbtn, eudr | Material master flags (`eudr_commodity`, `sbtn_high_impact_commodity`), mapping |
| `owner` | `owner:energy-manager-sakyla`, `owner:sourcing`, `owner:agronomy` | Domain → owner table (configured once) |
| `source_kind` | file, generated_doc, knowledge | Pipeline |
| `contributor` | `contributor:<person_id>` | Knowledge capture only |

`quality:flagged:<issue_type>` uses the package's issue types exactly: unit_error, duplicate_record, currency_error, material_mismatch, decimal_shift, missing_record, meter_spike, wrong_gas_code, certificate_mismatch, soil_misreport, outlier_implausible, area_mismatch, coordinate_swap, pcf_unit_error, pcf_stale_period, total_mismatch, missing_leg, mode_mislabel.

**File-level tag summary** (shown on every file card), e.g.:
`Säkylä · 2025 · energy · Scope 2 · 1,204 records · 3 flagged · owner: energy manager`

---

## 5. Graph model

### 5.1 Nodes
`File` · `Record` · `Site` · `Supplier` · `Material` · `Farm` · `Parcel` · `Catchment` · `EmissionFactor` · `Issue` · `Correction` · `Person` · `Knowledge` · `ReportLine`

### 5.2 Edges
| Edge | From → To | Example |
|---|---|---|
| `contains` | File → Record | erp file → erp:4500123:10 |
| `mentions` | Record → entity | erp line → SUP073, M110 |
| `supplies` | Supplier → Material | SUP073 → M154 |
| `receives` | Site → Material | S-KAN → M100 |
| `grows_on` | Farm → Parcel | F0001 → F0001-P01 |
| `located_in` | Parcel → Catchment | F0001-P01 → CA28 |
| `uses_factor` | Record → EmissionFactor | shipment leg → EF-… |
| `flagged_by` | Record → Issue | meter reading → meter_spike |
| `corrected_by` | Record → Correction | value fixed, reason, approver |
| `rolls_up_to` | Record → ReportLine | → Scope 3 cat 1 |
| `stated_by` | Knowledge → Person | K-0042 → Matti |
| `explains` | Knowledge → Record/entity | K-0042 → refrigerant records at S-SAK |
| `approved_by` | Correction/Knowledge → Person | → reviewer |
| `owns` | Person → domain | energy manager → energy |

### 5.3 Three views over one graph
1. **File map — "what came in, and where is the mess?"**
   Folders → files, coloured by domain, badge for quality status. Click a file → its tags, record count, flagged issues, owner.
2. **Entity view — "show me everything about X."**
   Click Säkylä → all files, records, suppliers, emissions, issues and knowledge linked to it. Click SUP073 → materials, PCF files across years, and whether the 2025 PCF is stale.
3. **Lineage view — "where does this number come from?"**
   Start at a report line (e.g. Scope 3 cat 1 = X t) → materials → ERP lines → factor used → source file → correction (with reason + approver) → knowledge items that explain it.

**Scale rule:** never render all 14,213 parcels. Cluster by farm / catchment / domain; expand on click. Default view shows ≤ ~300 nodes.

---

## 6. Ingestion pipeline

```
┌────────────┐  ┌──────────────┐  ┌───────────────┐  ┌─────────────┐  ┌────────────┐
│  Upload /  │→ │ Detect type  │→ │ Map columns / │→ │ Normalise   │→ │ Resolve IDs│
│  drop zone │  │ (schema match│  │ extract fields│  │ units, FX,  │  │ + auto-tag │
│  chat/voice│  │  + classifier│  │ (saved recipe)│  │ language    │  │ + edges    │
└────────────┘  └──────────────┘  └───────────────┘  └─────────────┘  └─────┬──────┘
                                                                             ▼
┌────────────┐  ┌──────────────┐  ┌───────────────┐                  ┌─────────────┐
│ Searchable │← │  Approved    │← │ Review queue  │←── low conf / ── │ Quality     │
│ + feeds    │  │  (logged)    │  │ (owner-routed)│    flagged       │ checks      │
│ inventory, │  └──────────────┘  └───────────────┘                  └─────────────┘
│ risk models│
└────────────┘
```

| Step | What happens | Notes |
|---|---|---|
| **1. Upload** | Drop zone (any file), folder watch (SharePoint/OneDrive in production), chat/voice for knowledge | Original stored unchanged; hash recorded |
| **2. Detect type** | Known schema → direct match. Unknown → LLM classifier proposes `doc_type` + target schema | Confidence score |
| **3. Map / extract** | Tabular: column mapping. Docs/images: OCR + LLM field extraction to target schema | **Mapping recipes**: first time a layout appears, AI proposes mapping, human confirms once; saved and reused deterministically |
| **4. Normalise** | kg/t (`uom = TO` → ×1000), kWh/MWh, currency → EUR, NCV conversions, Finnish/Swedish text → `material_id` | Every transformation logged |
| **5. Resolve + tag** | Extract IDs → tags → graph edges. Fuzzy entity resolution for free text ("Säkylän tehdas" → `S-SAK`) | Ambiguous matches → review |
| **6. Quality checks** | Rules + anomaly detection for the 18 issue types; cross-checks (GoO log vs registry, deliveries vs stock change) | **Legitimate edge cases not flagged**: credit notes, vessel lots in tonnes, seasonal meter peaks, ammonia systems |
| **7. Review queue** | Low-confidence extractions, flagged records, proposed corrections, new knowledge → routed to domain owner | Approve / edit / reject, with reason |
| **8. Approved** | Searchable, cited, feeds inventory + Track C models | Status `approved`, reviewer + timestamp |

### 6.1 Provenance fields (on every fact)
`fact_id, record_key, value, unit, source_file, source_hash, location (row / page / bbox / message_id), extraction_method (schema|mapping_recipe|llm|ocr|human), confidence, transformations[], issue_flags[], correction_id, status, reviewer, reviewed_at, tags[]`

---

## 7. Tacit knowledge capture (people as a data source)

### 7.1 Two ways in
**A. Deliberate — "Teach the bot"**
- Button or command in chat; **voice** via speech-to-text (Azure Speech / Whisper), transcript kept as source.
- Bot asks 1–2 short follow-ups to make it usable: *which site? since when? how sure are you?*

**B. Detected during conversation**
- The bot checks user statements against the knowledge base and data; statements that are **new, more specific, or contradicting** become candidates.
- No interruption: a **💡 "New knowledge found (n)"** chip appears beside the chat.
- Sessions may never end, so the bot offers to save at **natural pauses**: after the question is answered, after a few idle minutes, or when the chip is clicked:
  > *"You mentioned 2 things I didn't know. Add them to the knowledge base?"*  **[Add] [Edit] [Discard]** per item
- **Nothing is saved without the user's confirmation.** That confirmation is the first audit-trail entry.

### 7.2 Knowledge item schema
| Field | Example |
|---|---|
| `knowledge_id` | K-0042 |
| `statement` | "Old freezer line at Säkylä decommissioned March 2025" |
| `type` | fact · explanation (why a number looks odd) · process know-how · contact ("ask X about Y") |
| `tags` | `site:S-SAK` · `domain:refrigerants` · `year:2025` · `scope:1` (same taxonomy as §4) |
| `linked_entities` | graph edges (`explains`) to sites, records, suppliers… |
| `contributed_by` | person id + role (e.g. energy manager, Säkylä) |
| `source` | chat message id or voice transcript snippet + timestamp |
| `confidence` | user-stated: sure / think so / heard |
| `valid_from` / `valid_until` | so knowledge can expire |
| `status` | `pending_review` → `approved` / `rejected` / `superseded` |
| `reviewer`, `review_note`, `reviewed_at` | review trail |

### 7.3 Review and trust rules
- **Pending items are visible but marked.** The copilot may use them only with a label: *"According to Matti (unreviewed): …"*
- **Routed to the domain owner** (energy knowledge → energy manager).
- **Conflict check:** if knowledge contradicts data (e.g. "line decommissioned" but meter readings continue), both are flagged for the reviewer. People's knowledge becomes a data-quality signal.
- **Approved knowledge is evidence**, cited like a file row: *"Source: K-0042, stated by Matti (energy manager), approved by Anna, 7 Nov 2026."*
- **Knowledge annotates, never overwrites.** A measured value is only changed through the normal correction log.

### 7.4 Guardrails (state in method note)
- Only work-related facts are captured — no personal details.
- Contributors can see, edit and withdraw their own items.
- Every item shows who said it and who approved it.

### 7.5 "Who knows what"
`stated_by` edges build an expert map automatically: the bot can route a question or a data gap to the person most likely to know.

---

## 8. Retrieval & answering

### 8.1 Three ways to look things up
1. **Faceted search** — tick tags (`site:S-SAK` + `year:2025` + `quality:flagged`) → matching files, records, knowledge.
2. **Natural language** — "everything about Kantvik steam in 2025" → translated into tag filters; results show *why* they matched.
3. **Graph neighbours** — "what else is connected to this file / supplier / number?"

### 8.2 Copilot answering rules
| Question type | How it's answered |
|---|---|
| Numeric ("Scope 2 market-based 2025?") | Query over approved facts → computed value + calculation shown |
| Lookup ("which suppliers provide PCFs?") | Tag/graph query → list with record links |
| Explanatory ("why did X drop?") | Data + document retrieval + approved knowledge |
| Standards ("does L27 count as a reduction?") | Framework docs, cited by section |
| Not enough evidence | **Says so**, names the missing data and who to ask (→ §9.2) |

Every answer cites: file + row / record key / knowledge id / document section. Pending or flagged evidence is labelled as such.

---

## 9. Supporting features

### 9.1 Report-readiness dashboard
- Coverage by site × month × category; **"2025 report readiness: 87 %"**.
- To-do list: what's missing, owner, estimated impact on totals.
- Turns "scattered data" into a manageable project.

### 9.2 Missing-data chaser
- System knows what the inventory needs → detects gaps (e.g. `energy:S-KAN:2025-10:steam` missing).
- Drafts a message to the owner (Teams/email): *"Kantvik's October steam reading is missing — can you send it or reply here?"*
- The reply comes back through chat → becomes a record or knowledge item → review.

### 9.3 Closed loop
```
gap detected → right person asked → answer captured (file / chat / voice)
   → tagged + linked → reviewed → cited in reports and answers
```

---

## 10. Evaluation (reliability, 10 %)

| Test | Data | Metric |
|---|---|---|
| Extraction accuracy | `generated/` docs vs `ground_truth.csv` | Field-level accuracy per format; % errors caught by review queue |
| Issue detection | Package dev labels 2023–2024 (`tasks/dev/A1_dev_issue_labels_2023_2024.csv`) | Precision / recall per issue type (baseline: rules ≈ F1 0.53) |
| Inventory end-to-end | Dev truths 2023, 2024 | Error vs truth per category |
| Copilot | 3 dev questions + our own question set incl. **unanswerable** ones | Correct answers, citation rate, correct refusals |
| Knowledge capture | Scripted chats with planted new facts | Detection recall, false-suggestion rate |

---

## 11. Tech stack (hackathon) and Microsoft mapping

| Layer | Hackathon | Apetit production (Microsoft) |
|---|---|---|
| File intake | Drop zone + local folder | SharePoint / OneDrive libraries, Outlook, Teams |
| Extraction / OCR | LLM + OCR (e.g. Tesseract / vision model) | Azure AI Document Intelligence, Azure OpenAI |
| Speech | Whisper | Azure AI Speech |
| Facts store | DuckDB / SQLite | Fabric lakehouse / Azure SQL |
| Tags | Tag table | SharePoint metadata columns / Purview |
| Graph | NetworkX → JSON | Fabric / Cosmos DB (Gremlin) or Neo4j |
| Graph UI | Cytoscape.js or react-force-graph | Embedded web part / Power BI visual |
| Copilot | Tool-calling agent | Copilot Studio / Azure OpenAI, exposed via MCP or connector |
| Reports | Excel / CSV export | Power BI, Excel |

Pitch line: **"There is no connector to your data today — this layer is that connector, and it plugs into the Copilot you're already testing."**

---

## 12. Demo script (~3 minutes)

1. **The mess:** file map of the package — 10+ formats, red badges where planted issues were found.
2. **Upload:** drop a new 2025 supplier PCF → it attaches to `SUP073` + `M154` in the graph → flagged `pcf_stale_period` → lands in the sourcing owner's review queue.
3. **Paper note:** upload a (synthetic) photo of a waste transfer note → fields extracted → tagged `site · waste · 2025 · scope3:cat5` → approved.
4. **Lineage:** click the Scope 3 report line → trace down to that ERP line, its factor, the source file, and the logged correction.
5. **Tacit knowledge:** ask *"Why did refrigerant top-ups at site X change in 2025?"* → bot: *"The data shows it, but nothing explains it."* → user explains by voice → 💡 chip → **Add** → item tagged, linked, labelled *pending review* with contributor name → reviewer approves → ask again → cited answer naming contributor and reviewer.
   *(Use an illustrative example; the package lists ammonia systems as a legitimate edge case, so knowledge that explains such a case prevents a false alarm.)*
6. **Readiness:** dashboard shows 2025 readiness % and the missing-data chaser drafting a message to an owner.
7. **Close:** "Every input tagged and linked, every number traceable, every change approved by a person."

---

## 13. Build priority

| Priority | Item |
|---|---|
| **P0** | Ingest package raw feeds → facts store with provenance fields (§6.1) |
| **P0** | ID extraction + auto-tagging (§4) + graph build → JSON |
| **P0** | Graph UI: file map + entity view (§5.3), clustered |
| **P0** | Quality checks for main issue types + review queue with approve/reject |
| **P0** | Tacit knowledge capture: chat "teach" + detection chip + review (§7) |
| **P1** | Lineage view from report lines |
| **P1** | `messify.py` generated docs + extraction accuracy eval |
| **P1** | Copilot answering rules incl. refusals (§8.2) |
| **P1** | Voice input |
| **P2** | Readiness dashboard + missing-data chaser |
| **P2** | Mapping recipes for unseen layouts (live demo with a format nobody prepared) |

---

## Sources (package)
- `docs/DATA_DICTIONARY.md` — IDs and columns
- `docs/TASKS_AND_SCORING.md` — record-key formats, issue types, legitimate edge cases, jury rubric
- `docs/METHODOLOGY.md` — canonical tables, conversions, GoO rule, credit notes
- `docs/ASSUMPTIONS_AND_LIMITATIONS.md` — synthetic data caveats
- Challenge brief (Apetit × SinceAI 2026) — evaluation criteria, synthetic data allowed with stated assumptions
- Judges' Q&A transcript, 7 Nov 2026
