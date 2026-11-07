// Layer 1: the Overview is "today" on the demo clock. Four widgets that move day to day, each a statistic of the
// season so far (from /api/radar/today), each one button that opens its Layer 2. The 15-season outlook stays one
// tap away in the Long view strip (its sheets come from /api/radar/outlook).
import type { MouseEvent } from "react";
import { useToday } from "../api/hooks";
import type { Region } from "../api/types";
import { FieldsIcon, PinIcon, Segmented, SproutIcon, TrendIcon, WarnIcon } from "../components/ui";
import { CLIMATES, REGION_VIEW, useStore, type SheetKind } from "../state/store";
import { useTodayOutlook } from "./data";
import { OverviewSheets } from "./Sheets";
import { DemoClock } from "./today/DemoClock";
import { FarmSpread, spreadLine } from "./today/FarmSpread";
import { glanceLine, SeasonGlance } from "./today/SeasonGlance";
import { SinceYesterday } from "./today/SinceYesterday";
import { TodaySheets } from "./today/TodaySheets";
import { Unusual, unusualLine } from "./today/Unusual";
import { CROP_NAME, longDate, pathNote, stageLine } from "./today/shared";
import { rect, skel, Widget } from "./Widget";

export function Overview() {
  const climate = useStore((s) => s.climate);
  const setClimate = useStore((s) => s.setClimate);
  const asOf = useStore((s) => s.asOf);
  const sheet = useStore((s) => s.sheet);
  const openSheet = useStore((s) => s.openSheet);
  const setTab = useStore((s) => s.setTab);
  const setYear = useStore((s) => s.setYear);
  const setLens = useStore((s) => s.setLens);
  const flyTo = useStore((s) => s.flyTo);
  const q = useToday(asOf, climate);
  const outlook = useTodayOutlook();
  const t = q.data, o = outlook.data;
  const open = (k: SheetKind) => (e: MouseEvent) => openSheet(k, rect(e));
  const toMap = (lens: "overall" | "drought", region?: Region) => {
    if (t) setYear(+t.date.slice(0, 4));
    setLens(lens);
    if (region) flyTo(REGION_VIEW[region]);
    setTab("map");
  };
  const worst = t ? [...t.regions].sort((a, b) => b.dryness_pct - a.dryness_pct)[0]?.region : undefined;
  const crop = t ? CROP_NAME[t.crop] : "pea";

  return (
    <main className="page" aria-label="Overview">
      <div className="ov-head">
        <div>
          <div className="eyebrow">Today on the twin · {t ? pathNote(t) : "…"}</div>
          <h1 className="ov-title">{t ? longDate(t.date) : "…"}</h1>
          <p className="ov-sub">{t ? stageLine(t) : " "}</p>
        </div>
        <div className="ov-controls">
          <DemoClock t={t} fetching={q.isFetching} />
          <Segmented className="glass" label="Weather path after 2026" value={climate} onChange={setClimate}
            options={CLIMATES.map((c) => ({ key: c.key, label: c.label }))} />
        </div>
      </div>
      {q.error ? <p className="err" role="alert">Couldn't load today: {String(q.error)}</p> : null}

      <div className={`grid today ${sheet ? "dim" : ""}`} aria-hidden={sheet ? true : undefined}>
        <Widget size="M" label={`This season at a glance · ${crop}`} icon={<SproutIcon />} cta="Open the map" tour="glance"
          onOpen={() => toMap("overall", worst)}>
          {t ? <SeasonGlance t={t} /> : skel("100%", 110)}
          <span className="w-sub">{t ? glanceLine(t) : " "}</span>
        </Widget>

        <Widget size="M" label="What changed since yesterday" icon={<WarnIcon />} cta="See what changed" tour="changes"
          onOpen={open("changes")}>
          {t ? <SinceYesterday t={t} /> : skel("100%", 120)}
        </Widget>

        <Widget size="M" label="How unusual is this season?" icon={<TrendIcon />} cta="How we know" tour="unusual"
          right={<span className="muted">dryness since sowing</span>} onOpen={open("unusual")}>
          {t ? <Unusual regions={t.regions} /> : skel("100%", 110)}
          <span className="w-sub">{t ? unusualLine(t.regions) : " "}</span>
        </Widget>

        <Widget size="M" label={`How the farms are spread · ${crop}`} icon={<FieldsIcon />} cta="Show the driest farms"
          right={<span className="muted">dryness so far</span>} onOpen={() => toMap("drought", worst)}>
          {t ? <FarmSpread farms={t.farms} /> : skel("100%", 110)}
          <span className="w-sub">{t ? spreadLine(t.farms) : " "}</span>
        </Widget>
      </div>

      <button type="button" className={`longview glass ${sheet ? "dim" : ""}`} onClick={open("money")} data-tour="longview">
        <PinIcon /><span className="eyebrow">Long view</span>
        <span>{o ? `${o.years[0]}–${o.years[o.years.length - 1]}: ${o.money} a year at stake · ${o.costly_years} costly seasons` : "15 seasons ahead …"}</span>
        <span className="w-cta">See the outlook ›</span>
      </button>

      {o ? <OverviewSheets o={o} /> : null}
      <TodaySheets t={t} />
    </main>
  );
}
