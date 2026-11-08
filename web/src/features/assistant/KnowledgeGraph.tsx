// "What it knows": the assistant's knowledge graph. Nodes are coloured by kind and sized by log(records); the latest
// answer's nodes light up; people's notes get a ring (dashed until a second person confirms); gaps are hollow "?"s.
// Farms and sites are their own nodes, so notes and gaps about the same place group around one point.
// A freshly filed note plays its filing: tag chips one by one, then the node drops in and its edges draw.
// Clicking a node opens a drawer with everything linked to it (for a farm or site: src.r_entity.entity_view).
import { useEffect, useMemo, useRef, useState } from "react";
import { useEntity, useGraph } from "../../api/hooks";
import type { Filed, Graph, GraphNode } from "../../api/types";
import { useStore } from "../../state/store";

const W = 640, H = 620;
type P = { x: number; y: number };
type PV = P & { vx: number; vy: number };
const HUB = "crop:pea";
const FILL: Record<GraphNode["kind"], string> = {
  hub: "var(--kg-data)", data: "var(--kg-data)", model: "var(--kg-model)", doc: "var(--kg-doc)", tacit: "var(--kg-tacit)", gap: "transparent",
  entity: "var(--kg-entity)",
};
const KIND_LABEL: Record<GraphNode["kind"], string> = {
  hub: "Crop", data: "Measured data", model: "Model", doc: "Document", tacit: "Note from a person", gap: "Gap", entity: "Farm or site",
};
const GROUP_ORDER: GraphNode["kind"][] = ["entity", "data", "tacit", "gap", "model", "doc", "hub"];
const GROUP_LABEL: Record<GraphNode["kind"], string> = {
  entity: "Farms & sites", data: "Data tables", tacit: "People's notes", gap: "Gaps", model: "Models", doc: "Documents", hub: "Crop",
};
const REGION: Record<string, string> = { FI_SW: "SW Finland", SE_SKANE: "Skåne" };
const PILL = "unverified · needs a second person";

const radius = (n: GraphNode) =>
  n.kind === "hub" ? 34 : n.kind === "gap" ? 13 : n.kind === "tacit" ? 13 : n.kind === "entity" ? 15
    : n.records ? Math.max(12, Math.min(24, 6 + 3 * Math.log10(n.records + 1))) : n.kind === "model" ? 18 : 14;

/** Repulsion, springs and a gentle pull to the centre. Only `movable` nodes move (all of them when it is undefined). */
function relax(g: Graph, pos: Map<string, PV>, iters: number, movable?: Set<string>) {
  const ids = g.nodes.map((n) => n.id);
  const moves = (id: string) => id !== HUB && (!movable || movable.has(id));
  for (let it = 0; it < iters; it++) {
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
      const a = pos.get(ids[i])!, b = pos.get(ids[j])!;
      let dx = a.x - b.x, dy = a.y - b.y;
      const d2 = Math.max(dx * dx + dy * dy, 40), f = 5200 / d2, d = Math.sqrt(d2);
      dx /= d; dy /= d;
      a.vx += dx * f; a.vy += dy * f; b.vx -= dx * f; b.vy -= dy * f;
    }
    for (const e of g.edges) {
      const a = pos.get(e.source), b = pos.get(e.target);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y, d = Math.max(Math.hypot(dx, dy), 1), f = (d - 130) * 0.02;
      a.vx += (dx / d) * f; a.vy += (dy / d) * f; b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
    }
    for (const [id, p] of pos) {
      if (!moves(id)) { p.vx = p.vy = 0; continue; }
      p.vx += (W / 2 - p.x) * 0.004; p.vy += (H / 2 - p.y) * 0.004;
      p.x = Math.min(W - 60, Math.max(60, p.x + p.vx * 0.5)); p.y = Math.min(H - 40, Math.max(36, p.y + p.vy * 0.5));
      p.vx *= 0.6; p.vy *= 0.6;
    }
  }
  return new Map([...pos].map(([k, v]) => [k, { x: v.x, y: v.y }]));
}

/** A small deterministic force layout (same graph → same picture). */
function layout(g: Graph): Map<string, P> {
  const sector: Record<string, number> = { data: 0, model: 1.6, doc: 2.6, tacit: 4.0, entity: 4.5, gap: 5.0 };
  const pos = new Map<string, PV>();
  g.nodes.forEach((n, i) => {
    const a = (sector[n.kind] ?? 0) + i * 0.37, r = n.kind === "hub" ? 0 : n.kind === "gap" ? 250 : 170;
    pos.set(n.id, { x: W / 2 + r * Math.cos(a), y: H / 2 + r * Math.sin(a), vx: 0, vy: 0 });
  });
  return relax(g, pos, 320);
}

/** When nodes are added (a note was filed), keep everyone else where they were and settle only the newcomers. */
function grow(g: Graph, prev: Map<string, P>): Map<string, P> | null {
  if (g.nodes.filter((n) => prev.has(n.id)).length < g.nodes.length / 2) return null;
  const pos = new Map<string, PV>();
  const fresh = new Set<string>();
  g.nodes.forEach((n, i) => {
    const old = prev.get(n.id);
    if (old) { pos.set(n.id, { ...old, vx: 0, vy: 0 }); return; }
    const near = g.edges.flatMap((e) => (e.source === n.id ? [e.target] : e.target === n.id ? [e.source] : []))
      .map((id) => pos.get(id) ?? prev.get(id)).filter((p): p is P => !!p);
    const c = near.length ? { x: near.reduce((s, p) => s + p.x, 0) / near.length, y: near.reduce((s, p) => s + p.y, 0) / near.length } : { x: W / 2, y: H / 2 };
    pos.set(n.id, { x: c.x + 60 * Math.cos(i * 2.4), y: c.y + 60 * Math.sin(i * 2.4), vx: 0, vy: 0 });
    fresh.add(n.id);
  });
  return relax(g, pos, 220, fresh);
}

/** The tags a note was filed with, as chips in reading order: what it is about, where, then the topic. */
function filingChips(f: Filed): [string, string][] {
  const out: [string, string][] = [];
  for (const r of f.item.linked_refs) {
    if (/^[FS]\d{3,4}$/i.test(r)) out.push(["farm", r.toUpperCase()]);
    else if (/^S-[A-Z]{2,4}$/i.test(r)) out.push(["site", r.toUpperCase()]);
    else out.push(["record", r]);
  }
  const hasSite = out.some(([k]) => k === "site");
  for (const t of f.item.tags) {
    const [k, v] = [t.split(":", 1)[0], t.slice(t.indexOf(":") + 1)];
    if (k === "site" && hasSite) continue;
    out.push(k === "region" ? ["region", REGION[v] ?? v] : k === "link" ? ["linked", v] : [k, v]);
  }
  const rank = ["farm", "site", "record", "region", "topic", "domain", "crop", "linked"];
  return out.sort((a, b) => (rank.indexOf(a[0]) + 99) % 99 - (rank.indexOf(b[0]) + 99) % 99);
}

const neighbours = (g: Graph, id: string) =>
  g.edges.flatMap((e) => (e.source === id ? [e.target] : e.target === id ? [e.source] : []));

export function KnowledgeGraph() {
  const g = useGraph();
  const lit = useStore((s) => s.litNodes);
  const fresh = useStore((s) => s.newNodes);
  const mode = useStore((s) => s.mode);
  const send = useStore((s) => s.send);
  const filing = useStore((s) => s.filing);
  const playFiling = useStore((s) => s.playFiling);
  const focus = useStore((s) => s.focus);
  const setFocus = useStore((s) => s.setFocus);
  const [full, setFull] = useState(false);
  const data = g.data;
  const prev = useRef<Map<string, P> | null>(null);
  const pos = useMemo(() => (data ? (prev.current && grow(data, prev.current)) || layout(data) : new Map<string, P>()), [data]);
  useEffect(() => { if (pos.size) prev.current = pos; }, [pos]);

  // ── the filing animation: times are ms after the note was filed ──
  const fid = filing ? `tacit:${filing.f.note_id}` : null;
  const chips = useMemo(() => (filing ? filingChips(filing.f) : []), [filing]);
  const T = { path: chips.length * 150 + 100, drop: chips.length * 150 + 350, draw: chips.length * 150 + 800, pill: chips.length * 150 + 1300 };
  const done = T.pill + 600;
  const hasNode = !!(fid && data?.nodes.some((n) => n.id === fid));
  const chipBase = useMemo(() => (filing ? Date.now() - filing.at : 0), [filing]);
  const nodeBase = useMemo(() => (filing ? Date.now() - filing.at : 0), [filing, hasNode]);
  const [settled, setSettled] = useState<string | null>(null);
  useEffect(() => {
    if (!filing) return;
    const t = setTimeout(() => setSettled(filing.f.note_id), Math.max(0, done - (Date.now() - filing.at)));
    return () => clearTimeout(t);
  }, [filing, done]);
  const playing = !!filing && settled !== filing.f.note_id && chipBase < done;
  const chipDelay = (ms: number) => ({ animationDelay: `${Math.max(0, ms - chipBase)}ms` });
  const nodeDelay = (ms: number) => ({ animationDelay: `${Math.max(0, ms - nodeBase)}ms` });

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setFocus(null); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [setFocus]);

  const litSet = new Set(lit);
  const anyLit = litSet.size > 0;
  const c = data?.counts ?? {};
  const sub = playing
    ? "Filing a note: it tags it, finds what it's about, and links it there. Nobody types a tag."
    : !anyLit
      ? `${c.data ?? "…"} data files, ${c.model ?? "…"} models, ${c.doc ?? "…"} documents and ${c.tacit ?? "…"} note${c.tacit === 1 ? "" : "s"} from people, grouped by farm, site, crop and topic. Click any node.`
      : fresh.some((n) => litSet.has(n))
        ? "New: one note from a person, connected to what it's about. Dashed means unverified."
        : (() => { const n = lit.filter((x) => x !== HUB).length; return `Lit up: the ${n} thing${n === 1 ? "" : "s"} this answer used.`; })();
  const label = data ? `Knowledge graph: ${data.nodes.length} nodes. ${anyLit ? `${lit.length} lit by the latest answer.` : ""}` : "Knowledge graph loading";
  const edgeColor = mode === "teach" ? "var(--kg-tacit)" : "var(--leaf)";
  return (
    <aside className={`kg glass ${full ? "kg-full glass-strong" : ""}`} aria-label="What it knows" data-tour="graph">
      <div className="kg-head">
        <h2>What it knows</h2>
        <button type="button" className="link" onClick={() => setFull(!full)} aria-pressed={full}>{full ? "Close full view" : "Full view"}</button>
      </div>
      <p className="kg-sub" aria-live="polite">{sub}</p>
      <div className="kg-canvas">
        {filing ? (
          <div className="kg-filing" role="status" key={filing.f.note_id}>
            <div className="kg-filing-head">
              <span>{playing ? "Filing it itself…" : "Filed itself"}</span>
              <button type="button" className="kg-x" onClick={() => playFiling(null)} aria-label="Hide the filing">×</button>
            </div>
            <div className="kg-chips">
              {chips.map(([k, v], i) => (
                <span key={`${k}:${v}`} className={`kg-chip ${playing ? "pop" : ""}`} style={playing ? chipDelay(i * 150) : undefined}>
                  <b>{k}:</b>{v}
                </span>
              ))}
            </div>
            <div className={`kg-path ${playing ? "pop" : ""}`} style={playing ? chipDelay(T.path) : undefined}>→ {filing.f.path.join(" › ")}</div>
          </div>
        ) : null}
        {data ? (
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
            {data.edges.map((e, i) => {
              const a = pos.get(e.source), b = pos.get(e.target);
              if (!a || !b) return null;
              const on = litSet.has(e.source) && litSet.has(e.target);
              const tacit = e.source.startsWith("tacit:") || e.source.startsWith("gap:");
              if (playing && e.source === fid) {
                return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="kg-draw" pathLength={1}
                  stroke="var(--kg-tacit)" strokeWidth={3} style={nodeDelay(T.draw)} />;
              }
              return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={on ? (e.source.startsWith("tacit:") ? "var(--kg-tacit)" : edgeColor) : "var(--line-strong)"}
                strokeWidth={on ? 3 : 1.2} strokeDasharray={tacit ? "4 4" : undefined} opacity={anyLit && !on ? 0.35 : 0.9} />;
            })}
            {data.nodes.map((n) => {
              const p = pos.get(n.id);
              if (!p) return null;
              const r = radius(n), on = litSet.has(n.id), dim = anyLit && !on;
              const isFiling = n.id === fid;
              const isNew = fresh.includes(n.id) && !(isFiling && !n.verified);
              const click = n.kind === "gap" ? () => send(`Fill the gap: ${n.label}`, "teach", { gap: n.id }) : () => setFocus(n.id);
              const pillW = PILL.length * 6.4 + 20, pillX = Math.min(W - 8 - p.x, Math.max(8 - p.x, -pillW / 2));
              return (
                <g key={n.id} className={`node ${dim ? "dim" : ""} ${focus === n.id ? "focused" : ""}`} transform={`translate(${p.x},${p.y})`}
                  onClick={click} role="button" tabIndex={0}
                  aria-label={n.kind === "gap" ? `Gap: ${n.label} Ask someone` : `${KIND_LABEL[n.kind]}: ${n.label}. Show everything linked`}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); click(); } }}>
                  <title>{n.detail ?? `${n.label}${n.records ? ` · ${n.records.toLocaleString("en-GB")} records` : ""}`}</title>
                  <g className={isFiling && playing ? "kg-drop" : undefined} style={isFiling && playing ? nodeDelay(T.drop) : undefined}>
                    {on || focus === n.id ? <circle r={r + 8} fill={FILL[n.kind] === "transparent" ? "var(--kg-tacit)" : FILL[n.kind]} opacity={0.18} /> : null}
                    {n.kind === "gap" ? (
                      <>
                        <circle r={r} fill="rgba(255,255,255,.7)" stroke="var(--kg-tacit)" strokeWidth={1.5} strokeDasharray="3 3" />
                        <text textAnchor="middle" dy={4} className="gapt">?</text>
                      </>
                    ) : n.kind === "entity" ? (
                      <rect x={-r} y={-r} width={2 * r} height={2 * r} rx={6} fill="var(--surface)" stroke={FILL.entity} strokeWidth={2.5} />
                    ) : <circle r={r} fill={FILL[n.kind]} />}
                    {n.kind === "tacit" ? <circle r={r + 5} fill="none" stroke="var(--kg-tacit)" strokeWidth={2}
                      className={isFiling && !n.verified ? "kg-ants" : undefined} strokeDasharray={n.verified ? undefined : "3 3"} /> : null}
                    {n.kind === "hub" ? <text textAnchor="middle" dy={5} style={{ fill: "#fff", stroke: "none", fontWeight: 700 }}>{n.label}</text>
                      : <text textAnchor="middle" y={r + 18} className={n.kind === "gap" ? "gapt" : n.kind === "entity" ? "entt" : ""}>{n.label}</text>}
                  </g>
                  {isFiling && !n.verified ? (
                    <g className={playing ? "kg-pill" : undefined} style={playing ? nodeDelay(T.pill) : undefined}
                      transform={`translate(${pillX},${-r - 34})`}>
                      <rect width={pillW} height={22} rx={11} fill="var(--kg-tacit)" />
                      <text x={pillW / 2} y={15} textAnchor="middle" style={{ fill: "#fff", stroke: "none", fontWeight: 600, fontSize: 12 }}>{PILL}</text>
                    </g>
                  ) : isNew ? (
                    <g transform={`translate(${r + 4},${-r - 6})`}>
                      <rect width={40} height={20} rx={10} fill="var(--kg-tacit)" />
                      <text x={20} y={14} textAnchor="middle" style={{ fill: "#fff", stroke: "none", fontWeight: 600, fontSize: 12 }}>New</text>
                    </g>
                  ) : null}
                </g>
              );
            })}
          </svg>
        ) : <p className="muted" style={{ padding: 20 }}>{g.error ? String(g.error) : "Loading…"}</p>}
        {data && focus ? <NodeDrawer g={data} id={focus} onClose={() => setFocus(null)} onPick={setFocus} /> : null}
      </div>
      <div className="kg-legend">
        <span><i className="dot data" /> Measured data <b>{c.data ?? "…"}</b></span>
        <span><i className="dot model" /> Model runs <b>{c.model ?? "…"}</b></span>
        <span><i className="dot doc" /> Documents <b>{c.doc ?? "…"}</b></span>
        <span><i className="dot tacit" /> People's know-how <b>{c.tacit ?? "…"}</b></span>
        <span><i className="dot entity" /> Farms & sites <b>{c.entity ?? "…"}</b></span>
        <span className="gapl"><i className="dot gap" /> Gaps: ask someone <b>{c.gap ?? "…"}</b></span>
      </div>
    </aside>
  );
}

/** Everything linked to one node: its graph neighbours grouped by kind, and for a farm or site the entity view. */
function NodeDrawer({ g, id, onClose, onPick }: { g: Graph; id: string; onClose: () => void; onPick: (id: string) => void }) {
  const n = g.nodes.find((x) => x.id === id);
  const send = useStore((s) => s.send);
  const ent = useEntity(n?.kind === "entity" ? id.slice("entity:".length) : null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeRef.current?.focus(); }, [id]);
  if (!n) return null;
  const byId = new Map(g.nodes.map((x) => [x.id, x]));
  const near = [...new Set(neighbours(g, id))].map((x) => byId.get(x)).filter((x): x is GraphNode => !!x);
  const groups = GROUP_ORDER.map((k) => [k, near.filter((x) => x.kind === k)] as const).filter(([, xs]) => xs.length);
  const e = ent.data;
  const title = n.kind === "entity" ? (e?.name ? (e.name.startsWith(n.label) ? e.name : `${n.label} · ${e.name}`) : n.label) : n.kind === "tacit" ? "A note from a person" : n.label;
  return (
    <aside className="kg-drawer" role="dialog" aria-label={`About ${n.label}`}>
      <div className="kg-drawer-head">
        <div>
          <div className={`kg-eyebrow ${n.kind}`}>{n.kind === "entity" ? (e ? (e.kind === "farm" ? "Contract farm" : "Site") : "Farm or site") : KIND_LABEL[n.kind]}</div>
          <h3>{title}</h3>
        </div>
        <button ref={closeRef} type="button" className="kg-x" onClick={onClose} aria-label="Close">×</button>
      </div>

      {n.kind === "tacit" ? (
        <section>
          <p className="kg-quote">“{n.detail}”</p>
          <p className="kg-meta">{n.by ? `${n.by} · ` : ""}{n.verified ? "confirmed by a second person" : PILL}</p>
          {n.tags?.length ? <div className="kg-chips">{n.tags.map((t) => <span key={t} className="kg-chip"><b>{t.split(":")[0]}:</b>{t.slice(t.indexOf(":") + 1)}</span>)}</div> : null}
        </section>
      ) : null}
      {n.kind === "gap" ? (
        <section>
          <p className="kg-meta">Nobody has told it about {n.question ?? n.label.replace(/\?$/, "")}.</p>
          <button type="button" className="btn btn-tacit" onClick={() => send(`Fill the gap: ${n.label}`, "teach", { gap: n.id })}>Ask someone →</button>
        </section>
      ) : null}
      {n.kind === "data" && n.records ? <p className="kg-meta">{n.records.toLocaleString("en-GB")} records</p> : null}

      {n.kind === "entity" ? (
        ent.isLoading ? <p className="kg-meta">Gathering everything linked to {n.label}…</p>
          : ent.error ? <p className="kg-meta err">{String(ent.error)}</p>
            : e ? (
              <>
                <section>
                  <h4>In the data <span>{e.tables.length} table{e.tables.length === 1 ? "" : "s"}, linked by the ID {e.id}</span></h4>
                  <ul className="kg-list">
                    {e.tables.map((t) => (
                      <li key={t.table}><span>{t.label}</span><span className="kg-num">{t.rows.toLocaleString("en-GB")} row{t.rows === 1 ? "" : "s"}{t.years ? ` · ${t.years}` : ""}{t.issues ? ` · ${t.issues} flagged` : ""}</span></li>
                    ))}
                  </ul>
                </section>
                <section>
                  <h4>From people <span>{e.notes.length}</span></h4>
                  {e.notes.length ? (
                    <ul className="kg-list">
                      {e.notes.map((k) => (
                        <li key={k.knowledge_id} className="note">
                          <button type="button" className="kg-row" onClick={() => byId.has(`tacit:${k.knowledge_id}`) && onPick(`tacit:${k.knowledge_id}`)}>
                            <span>“{k.statement}”</span>
                            <span className="kg-meta">{k.contributed_by} · {k.status === "approved" ? `confirmed by ${k.reviewer}` : "unverified"}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="kg-meta">Nobody has said anything about {n.label} yet.</p>}
                </section>
                {e.gaps.length ? (
                  <section>
                    <h4>Open gaps <span>{e.gaps.length}</span></h4>
                    <ul className="kg-list">
                      {e.gaps.map((x) => (
                        <li key={x.gap_id}><button type="button" className="kg-row gap" onClick={() => send(`Fill the gap: ${x.label}`, "teach", { gap: x.gap_id })}>
                          <span>{x.label}</span><span className="kg-meta">Ask someone →</span></button></li>
                      ))}
                    </ul>
                  </section>
                ) : null}
              </>
            ) : null
      ) : null}

      {groups.length ? (
        <section>
          <h4>Linked in the graph</h4>
          {groups.map(([k, xs]) => (
            <div key={k} className="kg-group">
              <div className="kg-group-label"><i className={`dot ${k === "hub" ? "data" : k}`} /> {GROUP_LABEL[k]}</div>
              <div className="kg-links">
                {xs.map((x) => <button key={x.id} type="button" className="kg-link" onClick={() => onPick(x.id)}>{x.label}</button>)}
              </div>
            </div>
          ))}
        </section>
      ) : null}
      <p className="kg-foot">Linked by shared IDs and filing rules, not guessed. Synthetic data.</p>
    </aside>
  );
}
