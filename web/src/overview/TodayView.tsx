// "This season" on the Overview (task #127, Noa): the season so far on the demo clock's day, four widgets that move
// day to day, each a statistic from /api/radar/today and each one button that opens its sheet.
import type { MouseEvent } from "react";
import { useToday } from "../api/hooks";
import { useStore, type SheetKind } from "../state/store";
import { DemoClock } from "./today/DemoClock";
import { FarmSpread, spreadLine } from "./today/FarmSpread";
import { glanceLine, SeasonGlance } from "./today/SeasonGlance";
import { SinceYesterday } from "./today/SinceYesterday";
import { TodaySheets } from "./today/TodaySheets";
import { Unusual, unusualLine } from "./today/Unusual";
import { CROP_NAME, pathNote, stageLine } from "./today/shared";
import { rect, skel, Widget } from "./Widget";

export function TodayView() {
  const climate = useStore((s) => s.climate);
  const asOf = useStore((s) => s.asOf);
  const sheet = useStore((s) => s.sheet);
  const openSheet = useStore((s) => s.openSheet);
  const q = useToday(asOf, climate);
  const t = q.data;
  const open = (k: SheetKind) => (e: MouseEvent) => openSheet(k, rect(e));
  const crop = t ? CROP_NAME[t.crop] : "pea";

  return (
    <>
      <div className={`today-head ${sheet ? "dim" : ""}`}>
        <p className="ov-sub">{t ? `${stageLine(t)} · ${pathNote(t)}` : " "}</p>
        <DemoClock t={t} fetching={q.isFetching} />
      </div>
      {q.error ? <p className="err" role="alert">Couldn't load this season: {String(q.error)}</p> : null}

      <div className={`grid today ${sheet ? "dim" : ""}`} aria-hidden={sheet ? true : undefined}>
        <Widget size="M" label={`This season at a glance · ${crop}`} cta="Every crop today" tour="glance" onOpen={open("changes")}>
          {t ? <SeasonGlance t={t} /> : skel("100%", 110)}
          <span className="w-sub">{t ? glanceLine(t) : " "}</span>
        </Widget>

        <Widget size="M" label="What changed since yesterday" cta="See what changed" tour="changes" onOpen={open("changes")}>
          {t ? <SinceYesterday t={t} /> : skel("100%", 120)}
        </Widget>

        <Widget size="M" label="How unusual is this season?" cta="How we know" tour="unusual"
          right="dryness since sowing" onOpen={open("unusual")}>
          {t ? <Unusual regions={t.regions} /> : skel("100%", 110)}
          <span className="w-sub">{t ? unusualLine(t.regions) : " "}</span>
        </Widget>

        <Widget size="M" label={`How the farms are spread · ${crop}`} cta="Compare with normal" right="dryness so far" onOpen={open("unusual")}>
          {t ? <FarmSpread farms={t.farms} /> : skel("100%", 110)}
          <span className="w-sub">{t ? spreadLine(t.farms) : " "}</span>
        </Widget>
      </div>
      <TodaySheets t={t} />
    </>
  );
}
