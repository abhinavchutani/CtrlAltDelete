// ② What changed since yesterday: today's status ring over every region × contract crop, and the top two changes.
import type { Today } from "../../api/types";
import { Ring, StatusMark } from "../../components/ui";

export function SinceYesterday({ t }: { t: Today }) {
  const n = t.all.length, c = t.counts;
  const top = t.changes.slice(0, 2);
  return (
    <div className="since">
      <span className="w-row">
        <Ring size={84} stroke={12}
          label={`${n} crop-regions today: ${c.ok ?? 0} on track, ${c.watch ?? 0} to watch, ${c.risk ?? 0} in a bad year`}
          parts={[{ value: c.ok ?? 0, color: "var(--status-ok)" }, { value: c.watch ?? 0, color: "var(--status-watch)" },
            { value: c.risk ?? 0, color: "var(--status-risk)" }]} />
        <span className="since-fig">
          <span className="w-fig">{t.changes.length}</span>
          <span className="w-sub">of {n} region crops moved</span>
        </span>
      </span>
      {top.length ? (
        <span className="since-lines">
          {top.map((ch, i) => (
            <span key={i} className="since-line"><StatusMark status={ch.to_status} size={12} />{ch.text}</span>
          ))}
          {t.changes.length > 2 ? <span className="muted">+{t.changes.length - 2} more</span> : null}
        </span>
      ) : <span className="w-sub">Nothing moved since yesterday.</span>}
    </div>
  );
}
