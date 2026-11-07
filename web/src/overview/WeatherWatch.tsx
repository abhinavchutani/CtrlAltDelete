// "Next season's weather": month by month (April–August) rain vs the 1991–2020 normal in each region, with pea
// flowering (June) marked. From /api/weather/months on the chosen climate path: one plausible weather path, not a
// forecast. Bar colour uses the map's rain-lens rule (within −10 % on track, to −25 % watch, drier is bad).
import { useMonths } from "../api/hooks";
import type { Climate, MonthWeather, Region, Status } from "../api/types";
import { REGION_NAME, StatusMark } from "../components/ui";

export const MONTHS = [4, 5, 6, 7, 8];
export const FLOWERING = 6;
const MONTH_NAME = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const rainStatus = (pct: number): Status => (pct >= -10 ? "ok" : pct >= -25 ? "watch" : "risk");
const sign = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "0");

export function useSeasonWatch(year: number, climate: Climate) {
  const fi = useMonths("FI_SW", year, climate);
  const se = useMonths("SE_SKANE", year, climate);
  const pick = (ms?: MonthWeather[]) => (ms ?? []).filter((m) => MONTHS.includes(m.month));
  const regions: { region: Region; months: MonthWeather[] }[] = [
    { region: "FI_SW", months: pick(fi.data?.months) }, { region: "SE_SKANE", months: pick(se.data?.months) },
  ];
  // the region whose flowering month is driest leads the headline
  const lead = regions
    .map((r) => ({ ...r, june: r.months.find((m) => m.month === FLOWERING) }))
    .filter((r) => r.june)
    .sort((a, b) => a.june!.precip_anom_pct - b.june!.precip_anom_pct)[0];
  // the driest month of the season anywhere (the second line of the headline)
  const driest = regions.flatMap((r) => r.months.map((m) => ({ region: r.region, m })))
    .sort((a, b) => a.m.precip_anom_pct - b.m.precip_anom_pct)[0];
  return { regions, lead, driest, loading: fi.isLoading || se.isLoading };
}

function RegionBars({ region, months }: { region: Region; months: MonthWeather[] }) {
  const H = 28; // px each side of the zero line, at ±60 %
  const h = (p: number) => Math.min(H, (Math.abs(p) / 60) * H);
  return (
    <div className="ww-region">
      <span className="ww-name">{REGION_NAME[region]}</span>
      <div className="ww-bars" role="img"
        aria-label={`${REGION_NAME[region]} rain vs normal: ${months.map((m) => `${ABBR[m.month]} ${sign(m.precip_anom_pct)}%`).join(", ")}`}>
        {months.map((m) => {
          const p = m.precip_anom_pct;
          return (
            <div key={m.month} className={`ww-col ${m.month === FLOWERING ? "flower" : ""}`}>
              <span className="ww-val">{sign(p)}%</span>
              <div className="ww-plot" style={{ height: 2 * H }}>
                <div className={`bar ${rainStatus(p)}`} style={p >= 0
                  ? { position: "absolute", bottom: H, height: Math.max(2, h(p)) }
                  : { position: "absolute", top: H, height: Math.max(2, h(p)) }} />
                <i className="ww-zero" style={{ top: H }} />
              </div>
              <span className="yl">{ABBR[m.month]}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** The widget body: a headline about flowering rain, then both regions' months. */
export function WeatherWatch({ year, climate }: { year: number; climate: Climate }) {
  const w = useSeasonWatch(year, climate);
  if (w.loading) return <div className="minimap skeleton" />;
  const j = w.lead?.june;
  const s = j ? rainStatus(j.precip_anom_pct) : "ok";
  return (
    <>
      {j && w.lead ? (
        <span className="ww-head">
          <StatusMark status={s} size={14} />
          <span>{s === "ok"
            ? <>Pea flowering (June) looks <b>close to normal</b> in both regions.</>
            : <><b>{REGION_NAME[w.lead.region]}</b>: June rain {sign(j.precip_anom_pct)}% at pea flowering, {s === "watch" ? "worth watching" : "drought risk"}.</>}
            {w.driest && w.driest.m.month !== FLOWERING && rainStatus(w.driest.m.precip_anom_pct) !== "ok"
              ? <> Driest: {REGION_NAME[w.driest.region]} {MONTH_NAME[w.driest.m.month]}, <b>{sign(w.driest.m.precip_anom_pct)}%</b>.</> : null}
          </span>
        </span>
      ) : null}
      <div className="ww">
        {w.regions.map((r) => <RegionBars key={r.region} region={r.region} months={r.months} />)}
      </div>
    </>
  );
}
