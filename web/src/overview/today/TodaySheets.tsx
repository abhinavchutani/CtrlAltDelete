// Layer 2 + 3 for the Today widgets: what changed (every crop) and how unusual (dryness and heat, any crop).
import { useState } from "react";
import { useToday } from "../../api/hooks";
import type { Today, TodayCrop } from "../../api/types";
import { Assumption, Crumbs, Receipt, REGION_NAME, Segmented, Sheet, STATUS_LABEL, StatusMark } from "../../components/ui";
import { useStore } from "../../state/store";
import { DotStrip } from "./Unusual";
import { below, CROP_NAME, longDate, ordinal, pathNote, STAGE_WORD } from "./shared";

const RULE = "A crop is ◆ bad year when its dryness or heat so far is at the 90th percentile of the same day in 1991–2020 " +
  "or beyond, once it has started flowering; ▲ watch from the 75th (from the 90th before flowering).";

function Foot({ t }: { t: Today }) {
  return <>{pathNote(t)}. Normal = {t.normal_years[0]}–{t.normal_years[1]}, same day of the season. Synthetic data pack, not Apetit's real figures.</>;
}

function ChangesSheet({ t, onClose }: { t: Today; onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  return (
    <Sheet label="What changed since yesterday" from={sheet?.from} onClose={onClose}>
      <div className="sheet-head"><div>
        <Crumbs items={[{ label: "Overview", onClick: onClose }, { label: "Since yesterday" }]} />
        <h2 className="sheet-title">{t.changes.length ? `${t.changes.length} ${t.changes.length === 1 ? "change" : "changes"} since yesterday` : "Nothing moved since yesterday"}</h2>
        <p className="sheet-sub">{longDate(t.date)} against the day before, every region × contract crop.</p>
      </div></div>
      {t.changes.length ? (
        <ul className="change-list">
          {t.changes.map((c, i) => (
            <li key={i}><StatusMark status={c.to_status} size={15} /><span>{c.text}</span>
              <span className="muted">{c.kind === "jump" ? "big move" : c.kind === "stage" ? "new stage" : c.kind}</span></li>
          ))}
        </ul>
      ) : null}
      <table className="today-table">
        <caption className="eyebrow">Every crop today</caption>
        <thead><tr><th>Region · crop</th><th>Stage</th><th>Status</th><th>Dryness</th><th>Heat</th></tr></thead>
        <tbody>
          {t.all.map((r) => (
            <tr key={r.region + r.crop}>
              <td>{REGION_NAME[r.region]} {CROP_NAME[r.crop]}</td>
              <td>{STAGE_WORD[r.stage]}</td>
              <td><span className="cell-status"><StatusMark status={r.status} size={13} label /></span></td>
              <td>{ordinal(r.dryness_pct)}</td>
              <td>{ordinal(r.heat_pct)} · {r.hot_days} hot days</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="sheet-sub" style={{ margin: "16px 0" }}>{RULE}</p>
      <Receipt sources={t.sources} foot={<Foot t={t} />} />
    </Sheet>
  );
}

function UnusualSheet({ t: t0, onClose }: { t: Today; onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  const climate = useStore((s) => s.climate);
  const [crop, setCrop] = useState<TodayCrop>(t0.crop);
  const q = useToday(t0.date, climate, crop);
  const t = q.data ?? t0;
  const crops = [...new Set(t0.all.map((r) => r.crop))];
  return (
    <Sheet label="How unusual is this season" from={sheet?.from} onClose={onClose}>
      <div className="sheet-head"><div>
        <Crumbs items={[{ label: "Overview", onClick: onClose }, { label: "How unusual" }]} />
        <h2 className="sheet-title">This season so far vs 30 normal seasons</h2>
        <p className="sheet-sub">Each dot is one year of 1991–2020 on {longDate(t.date).replace(/ \d{4}$/, "")}; the big dot is this season. Right = more stress.</p>
      </div>
      <Segmented label="Crop" value={crop} onChange={setCrop} options={crops.map((c) => ({ key: c, label: CROP_NAME[c] }))} /></div>
      {t.regions.map((r) => (
        <section key={r.region} className="unusual-block">
          <h3 className="group-h eyebrow"><StatusMark status={r.status} size={13} />{REGION_NAME[r.region]} {CROP_NAME[r.crop]} · {STAGE_WORD[r.stage]} · {STATUS_LABEL[r.status]}</h3>
          <div className="unusual-pair">
            <div><div className="k">Dryness since sowing · {ordinal(r.dryness_pct)} percentile</div>
              <DotStrip r={r} metric="dryness" height={56} />
              <div className="s">Drier than {below(r.dryness, r.dryness_normal)} of {r.dryness_normal.length} normal seasons ({Math.round(r.dryness * 100)}% of water demand unmet)</div></div>
            <div><div className="k">Hot days (≥ 27 °C) at flowering · {ordinal(r.heat_pct)} percentile</div>
              <DotStrip r={r} metric="heat" height={56} />
              <div className="s">{r.hot_days} so far; a normal season has {r.hot_days_p50} by this day</div></div>
          </div>
        </section>
      ))}
      {t.path !== "historical" ? <Assumption>{pathNote(t)}: one realisation of that climate future, so read it as a plausible season, not a prediction.</Assumption> : null}
      <p className="sheet-sub" style={{ margin: "16px 0" }}>{RULE}</p>
      <Receipt sources={t.sources} foot={<Foot t={t} />} />
    </Sheet>
  );
}

/** Opens the Today sheets; returns null for the other kinds (OverviewSheets handles those). */
export function TodaySheets({ t }: { t: Today | undefined }) {
  const sheet = useStore((s) => s.sheet);
  const close = useStore((s) => s.closeSheet);
  if (!sheet || !t) return null;
  if (sheet.kind === "changes") return <ChangesSheet t={t} onClose={close} />;
  if (sheet.kind === "unusual") return <UnusualSheet t={t} onClose={close} />;
  return null;
}
