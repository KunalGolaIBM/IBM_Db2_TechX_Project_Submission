import { useEffect, useRef, useState } from "react";
import { fmt, type SeriesPoint } from "../api";

/* Recall@10 or rows returned vs share of rows visible. One y axis per chart (small multiples, never dual axis).
   Palette validated with the dataviz validator: the control series is a deliberate neutral, also dashed and
   direct-labelled, so identity never rests on colour alone. */
export const SERIES = [
  { key: "rcac", label: "RCAC user, shared plan", color: "#c4251c", dash: undefined },
  { key: "where", label: "Plain WHERE, no RCAC", color: "#5d6569", dash: "5 4" },
  { key: "router", label: "NEEDLE router", color: "#009aa6", dash: undefined },
] as const;
type Key = (typeof SERIES)[number]["key"];

const H = 260, M = { t: 14, r: 16, b: 44, l: 44 };
const XT = [10, 25, 50, 75, 100];

export default function RecallChart({ data, metric, title, annotate = false }: {
  data: Record<Key, SeriesPoint[]>; metric: "recall" | "rows"; title: string; annotate?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  // Draw at the real pixel width so 11px text stays 11px (no viewBox scaling).
  const box = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(520);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const yMax = metric === "recall" ? 1 : 10;
  const yt = metric === "recall" ? [0, 0.25, 0.5, 0.75, 1] : [0, 2.5, 5, 7.5, 10];
  const x = (v: number) => M.l + ((v - 0) / 100) * (W - M.l - M.r);
  const y = (v: number) => M.t + (1 - v / yMax) * (H - M.t - M.b);
  const fmtY = (v: number) => (metric === "recall" ? fmt.dec(v, 2) : fmt.dec(v, 1));
  const at = (k: Key, i: number) => data[k][i];

  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 text-sm font-semibold">{title}</figcaption>
      <div className="relative" ref={box}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block" role="img"
          aria-label={`${title} against percent of rows visible, three series`} onMouseLeave={() => setHover(null)}>
          {yt.map((t) => (
            <g key={t}>
              <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="#dde3e5" strokeWidth={1} />
              <text x={M.l - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-mute font-mono text-[11px]">{metric === "recall" ? t.toFixed(2) : t}</text>
            </g>
          ))}
          {XT.map((t) => (
            <text key={t} x={x(t)} y={H - M.b + 18} textAnchor="middle" className="fill-mute font-mono text-[11px]">{t}%</text>
          ))}
          <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" className="fill-mute text-[11px]">share of rows the analyst may see</text>
          {hover != null && <line x1={x(XT[hover])} x2={x(XT[hover])} y1={M.t} y2={H - M.b} stroke="#101213" strokeOpacity={0.25} />}
          {SERIES.map((s) => {
            const pts = data[s.key];
            const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.x).toFixed(1)},${y(p[metric]).toFixed(1)}`).join(" ");
            return (
              <g key={s.key}>
                <path d={d} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dash} strokeLinejoin="round" />
                {pts.map((p, i) => (
                  <circle key={i} cx={x(p.x)} cy={y(p[metric])} r={hover === i ? 5 : 3.5} fill={s.color} stroke="#fbfcfd" strokeWidth={2} />
                ))}
              </g>
            );
          })}
          {annotate && (() => {
            const a = data.rcac[0], b = data.router[0];
            const ax = x(a.x) + 14, y1 = y(a[metric]), y2 = y(b[metric]);
            return (
              <g aria-hidden>
                <path d={`M${ax - 6},${y1} H${ax} V${y2 + 6} M${ax - 4},${y2 + 10} L${ax},${y2 + 4} L${ax + 4},${y2 + 10}`} fill="none" stroke="#101213" strokeWidth={1.25} />
                <text x={ax + 8} y={y1 + 20} dy="-0.2em" className="fill-ink font-mono text-[12px] font-semibold" stroke="#f3f7f9" strokeWidth={5} paintOrder="stroke" strokeLinejoin="round">{fmtY(a[metric])} → {fmtY(b[metric])}</text>
                <text x={ax + 8} y={y1 + 20} dy="1.1em" className="fill-mute text-[11px]" stroke="#f3f7f9" strokeWidth={5} paintOrder="stroke" strokeLinejoin="round">at {Math.round(a.x)}% visible, with the router</text>
              </g>
            );
          })()}
          {XT.map((t, i) => (
            <rect key={t} x={x(t) - 28} y={M.t} width={56} height={H - M.t - M.b} fill="transparent"
              onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={0} aria-label={`${t}% visible`} />
          ))}
        </svg>
        {hover != null && (
          <div className="pointer-events-none absolute top-2 z-10 min-w-[13rem] rounded-[6px] border border-hair bg-paper px-3 py-2 text-xs shadow-[0_2px_8px_rgba(16,18,19,.08)]"
            style={{ left: `${Math.min(70, Math.max(2, (x(XT[hover]) / W) * 100 - 12))}%` }}>
            <p className="mb-1 font-semibold">{XT[hover]}% of rows visible</p>
            {SERIES.map((s) => (
              <p key={s.key} className="flex items-center justify-between gap-4">
                <span className="flex items-center gap-1.5 text-ink-2"><Swatch color={s.color} dash={s.dash} />{s.label}</span>
                <span className="font-mono text-ink num">{fmtY(at(s.key, hover)[metric])}</span>
              </p>
            ))}
          </div>
        )}
      </div>
    </figure>
  );
}

export function Swatch({ color, dash }: { color: string; dash?: string }) {
  return (
    <svg width="18" height="8" aria-hidden className="shrink-0">
      <line x1="1" x2="17" y1="4" y2="4" stroke={color} strokeWidth="2" strokeDasharray={dash ? "4 3" : undefined} />
    </svg>
  );
}

export function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
      {SERIES.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5"><Swatch color={s.color} dash={s.dash} />{s.label}</li>
      ))}
    </ul>
  );
}
