// Weather you can see on the map: rain streaks, dry dust and a heat haze, driven by the API's weather for the
// region in view. With an alert open it shows that alert's month; otherwise the growing season (Apr–Sep) of the year.
// Purely visual: the strength of each effect follows the data, and the chip says the numbers in words.
import { useEffect, useMemo, useRef } from "react";
import { climateFor, useActiveScenario, useMonths, useWeather } from "../../api/hooks";
import { START_YEAR, useStore } from "../../state/store";
import { REGION_NAME } from "../fieldradar/useFieldData";

const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const clamp = (x: number) => Math.max(0, Math.min(1, x));
const signed = (n: number, unit: string) => `${n > 0 ? "+" : ""}${n}${unit}`;
type Drop = { x: number; y: number; v: number; len: number };
type Mote = { x: number; y: number; vx: number; vy: number; r: number };

export function WeatherFx() {
  const on = useStore((s) => s.weatherFx);
  const region = useStore((s) => s.viewRegion);
  const year = useStore((s) => s.year);
  const alert = useStore((s) => s.selectedAlert);
  const sim = useActiveScenario();
  const climate = sim.data?.spec.climate;
  const frame = useWeather(climateFor(year, climate, START_YEAR), year);
  const focusMonth = alert && alert.region === region && alert.year === year ? alert.month ?? null : null;
  const months = useMonths(focusMonth ? region : null, year, climate);

  const fx = useMemo(() => {
    const m = focusMonth ? months.data?.months.find((x) => x.month === focusMonth) : undefined;
    if (m) {
      return {
        rain: clamp((m.precip_anom_pct - 5) / 60), dry: clamp((-m.precip_anom_pct - 20) / 50),
        heat: clamp((m.tmean_anom_c - 0.5) / 2 + m.hot_days / 6),
        text: `${MONTH_LONG[m.month - 1]} ${year} · ${REGION_NAME[region]}: rain ${signed(m.precip_anom_pct, " %")} vs normal · `
          + `${m.tmean_c} °C (${signed(m.tmean_anom_c, " °C")})${m.hot_days >= 1 ? ` · ${m.hot_days} hot days` : ""}`,
      };
    }
    const cs = (frame.data?.cells ?? []).filter((c) => c.region === region);
    if (!cs.length) return null;
    const avg = (f: (c: (typeof cs)[number]) => number) => cs.reduce((s, c) => s + f(c), 0) / cs.length;
    const rain = Math.round(avg((c) => c.precip_anom_pct)), t = Math.round(avg((c) => c.tmax_anom_c) * 10) / 10;
    const drought = avg((c) => c.drought_index), hot = Math.round(avg((c) => c.hot_days_flowering) * 10) / 10;
    const dryWord = drought >= 0.65 ? "very dry at flowering" : drought >= 0.45 ? "dry at flowering" : "moist at flowering";
    return {
      rain: clamp((rain - 5) / 45), dry: clamp((drought - 0.4) / 0.35), heat: clamp((t - 0.4) / 1.6 + hot / 8),
      text: `${year} season · ${REGION_NAME[region]}: rain ${signed(rain, " %")} vs normal · ${signed(t, " °C")} · ${dryWord}`
        + `${hot >= 1 ? ` · ${hot} hot days at flowering` : ""}`,
    };
  }, [focusMonth, months.data, frame.data, region, year]);

  const canvas = useRef<HTMLCanvasElement>(null);
  const target = useRef({ rain: 0, dry: 0 });
  target.current = { rain: on && fx ? fx.rain : 0, dry: on && fx ? fx.dry : 0 };

  useEffect(() => {
    const cv = canvas.current;
    if (!cv || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = cv.getContext("2d")!;
    let w = 0, h = 0, raf = 0, last = performance.now();
    const drops: Drop[] = [], motes: Mote[] = [];
    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = cv.clientWidth; h = cv.clientHeight;
      cv.width = w * dpr; cv.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cv);
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      // ease the particle counts toward the data (no popping when the year changes)
      const wantDrops = Math.round(target.current.rain * 420), wantMotes = Math.round(target.current.dry * 90);
      if (drops.length < wantDrops) for (let i = 0; i < Math.min(12, wantDrops - drops.length); i++)
        drops.push({ x: Math.random() * (w + 200), y: Math.random() * -h, v: 900 + Math.random() * 500, len: 12 + Math.random() * 16 });
      else if (drops.length > wantDrops) drops.splice(0, Math.min(12, drops.length - wantDrops));
      if (motes.length < wantMotes) motes.push({ x: Math.random() * w, y: Math.random() * h, vx: 12 + Math.random() * 22,
        vy: -4 + Math.random() * 8, r: 0.8 + Math.random() * 1.8 });
      else if (motes.length > wantMotes) motes.splice(0, 1);
      ctx.clearRect(0, 0, w, h);
      if (drops.length) {
        ctx.strokeStyle = "rgba(190, 210, 235, 0.32)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (const d of drops) {
          d.y += d.v * dt; d.x -= d.v * 0.18 * dt;
          if (d.y > h + 30) { d.y = -30 - Math.random() * 120; d.x = Math.random() * (w + 200); }
          ctx.moveTo(d.x, d.y); ctx.lineTo(d.x + d.len * 0.18, d.y - d.len);
        }
        ctx.stroke();
      }
      if (motes.length) {
        ctx.fillStyle = "rgba(232, 196, 140, 0.28)";
        for (const m of motes) {
          m.x += m.vx * dt; m.y += m.vy * dt + Math.sin(now / 900 + m.x / 80) * 0.15;
          if (m.x > w + 10) { m.x = -10; m.y = Math.random() * h; }
          ctx.beginPath(); ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2); ctx.fill();
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, []);

  const vars = { "--rain": on && fx ? fx.rain : 0, "--dry": on && fx ? fx.dry : 0, "--heat": on && fx ? fx.heat : 0 } as React.CSSProperties;
  return (
    <>
      <div className="wx" style={vars} aria-hidden="true">
        <div className="wx-dry" /><div className="wx-heat" /><div className="wx-rain" />
        <canvas ref={canvas} className="wx-canvas" />
      </div>
      {on && fx ? <div className="wx-chip" role="status">{fx.text}</div> : null}
    </>
  );
}
