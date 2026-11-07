// "What it knows": the assistant's knowledge graph. Nodes are coloured by kind and sized by log(records); the latest
// answer's nodes light up; people's notes get a ring (dashed until a second person confirms); gaps are hollow "?"s.
import { useMemo, useState } from "react";
import { useGraph } from "../../api/hooks";
import type { Graph, GraphNode } from "../../api/types";
import { useStore } from "../../state/store";

const W = 640, H = 620;
const FILL: Record<GraphNode["kind"], string> = {
  hub: "var(--kg-data)", data: "var(--kg-data)", model: "var(--kg-model)", doc: "var(--kg-doc)", tacit: "var(--kg-tacit)", gap: "transparent",
};
const radius = (n: GraphNode) =>
  n.kind === "hub" ? 34 : n.kind === "gap" ? 13 : n.kind === "tacit" ? 13
    : n.records ? Math.max(12, Math.min(24, 6 + 3 * Math.log10(n.records + 1))) : n.kind === "model" ? 18 : 14;

/** A small deterministic force layout (same graph → same picture): repulsion, springs, gentle pull to the centre. */
function layout(g: Graph): Map<string, { x: number; y: number }> {
  const sector: Record<string, number> = { data: 0, model: 1.6, doc: 2.6, tacit: 4.0, gap: 5.0 };
  const pos = new Map<string, { x: number; y: number; vx: number; vy: number }>();
  g.nodes.forEach((n, i) => {
    const a = (sector[n.kind] ?? 0) + i * 0.37, r = n.kind === "hub" ? 0 : n.kind === "gap" ? 250 : 170;
    pos.set(n.id, { x: W / 2 + r * Math.cos(a), y: H / 2 + r * Math.sin(a), vx: 0, vy: 0 });
  });
  const ids = g.nodes.map((n) => n.id);
  for (let it = 0; it < 320; it++) {
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
      if (id === "crop:pea") { p.x = W / 2; p.y = H / 2; p.vx = p.vy = 0; continue; }
      p.vx += (W / 2 - p.x) * 0.004; p.vy += (H / 2 - p.y) * 0.004;
      p.x = Math.min(W - 60, Math.max(60, p.x + p.vx * 0.5)); p.y = Math.min(H - 40, Math.max(36, p.y + p.vy * 0.5));
      p.vx *= 0.6; p.vy *= 0.6;
    }
  }
  return new Map([...pos].map(([k, v]) => [k, { x: v.x, y: v.y }]));
}

export function KnowledgeGraph() {
  const g = useGraph();
  const lit = useStore((s) => s.litNodes);
  const fresh = useStore((s) => s.newNodes);
  const mode = useStore((s) => s.mode);
  const send = useStore((s) => s.send);
  const [full, setFull] = useState(false);
  const pos = useMemo(() => (g.data ? layout(g.data) : new Map()), [g.data]);
  const data = g.data;
  const litSet = new Set(lit);
  const anyLit = litSet.size > 0;
  const c = data?.counts ?? {};
  const sub = !anyLit
    ? `${c.data ?? "…"} data files, ${c.model ?? "…"} models, ${c.doc ?? "…"} documents and ${c.tacit ?? "…"} notes from people, organised by crop, place and topic.`
    : fresh.some((n) => litSet.has(n))
      ? "New: one note from a person, connected to what it's about. Dashed means unverified."
      : (() => { const n = lit.filter((x) => x !== "crop:pea").length; return `Lit up: the ${n} thing${n === 1 ? "" : "s"} this answer used.`; })();
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
        {data ? (
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
            {data.edges.map((e, i) => {
              const a = pos.get(e.source), b = pos.get(e.target);
              if (!a || !b) return null;
              const on = litSet.has(e.source) && litSet.has(e.target);
              const tacit = e.source.startsWith("tacit:") || e.source.startsWith("gap:");
              return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={on ? (e.source.startsWith("tacit:") ? "var(--kg-tacit)" : edgeColor) : "var(--line-strong)"}
                strokeWidth={on ? 3 : 1.2} strokeDasharray={tacit ? "4 4" : undefined} opacity={anyLit && !on ? 0.35 : 0.9} />;
            })}
            {data.nodes.map((n) => {
              const p = pos.get(n.id);
              if (!p) return null;
              const r = radius(n), on = litSet.has(n.id), dim = anyLit && !on;
              const isNew = fresh.includes(n.id);
              const click = n.kind === "gap" ? () => send(`Fill the gap: ${n.label}`, "teach", { gap: n.id }) : undefined;
              return (
                <g key={n.id} className={`node ${dim ? "dim" : ""}`} transform={`translate(${p.x},${p.y})`}
                  onClick={click} role={click ? "button" : undefined} tabIndex={click ? 0 : undefined}
                  aria-label={click ? `Gap: ${n.label} Ask someone` : undefined}
                  onKeyDown={click ? (e) => { if (e.key === "Enter" || e.key === " ") click(); } : undefined}>
                  <title>{n.detail ?? `${n.label}${n.records ? ` · ${n.records.toLocaleString("en-GB")} records` : ""}`}</title>
                  {on ? <circle r={r + 8} fill={FILL[n.kind]} opacity={0.18} /> : null}
                  {n.kind === "gap" ? (
                    <>
                      <circle r={r} fill="rgba(255,255,255,.7)" stroke="var(--kg-tacit)" strokeWidth={1.5} strokeDasharray="3 3" />
                      <text textAnchor="middle" dy={4} className="gapt">?</text>
                    </>
                  ) : <circle r={r} fill={FILL[n.kind]} />}
                  {n.kind === "tacit" ? <circle r={r + 5} fill="none" stroke="var(--kg-tacit)" strokeWidth={2} strokeDasharray={n.verified ? undefined : "3 3"} /> : null}
                  {n.kind === "hub" ? <text textAnchor="middle" dy={5} style={{ fill: "#fff", stroke: "none", fontWeight: 700 }}>{n.label}</text>
                    : <text textAnchor="middle" y={r + 18} className={n.kind === "gap" ? "gapt" : ""}>{n.label}</text>}
                  {isNew ? (
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
      </div>
      <div className="kg-legend">
        <span><i className="dot data" /> Measured data <b>{c.data ?? "…"}</b></span>
        <span><i className="dot model" /> Model runs <b>{c.model ?? "…"}</b></span>
        <span><i className="dot doc" /> Documents <b>{c.doc ?? "…"}</b></span>
        <span><i className="dot tacit" /> People's know-how <b>{c.tacit ?? "…"}</b></span>
        <span className="gapl"><i className="dot gap" /> Gaps: ask someone <b>{c.gap ?? "…"}</b></span>
      </div>
    </aside>
  );
}
