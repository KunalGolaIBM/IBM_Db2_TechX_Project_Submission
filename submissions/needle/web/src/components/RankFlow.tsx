import { useEffect, useMemo, useRef, useState } from "react";
import type { Mode, TriageResult } from "../api";

/* Rank flow: each advisory's keyword rank -> vector rank -> fused hybrid rank, one line per advisory, axes aligned
   with the three ranked columns below. Petrol = in both legs' top k; grey = one leg only; the bottom lane is
   "outside this leg's top k". Hover links to the columns through `hot`. Data: result.rankings only. */
const ORDER: Mode[] = ["keyword", "vector", "hybrid"];

export default function RankFlow({ result, hot, onHot }: { result: TriageResult; hot: string | null; onHot: (id: string | null) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(900);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(600, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const k = result.k;
  const lines = useMemo(() => {
    const rank: Record<Mode, Map<string, number>> = { keyword: new Map(), vector: new Map(), hybrid: new Map() };
    for (const m of ORDER) result.rankings[m].forEach((r) => rank[m].set(r.id, r.rank));
    const ids = [...new Set(ORDER.flatMap((m) => result.rankings[m].map((r) => r.id)))];
    return ids.map((id) => {
      const rs = ORDER.map((m) => rank[m].get(id) ?? null);
      return { id, rs, both: rs[0] != null && rs[1] != null, inHybrid: rs[2] != null };
    }).sort((a, b) => Number(a.both) - Number(b.both)); // agreeing lines drawn last, on top
  }, [result]);

  const H = 210, top = 14, laneGap = 22, bottom = 26;
  const rowH = (H - top - bottom - laneGap) / Math.max(1, k - 1);
  const outY = H - bottom;
  const xs = [w / 6, w / 2, (5 * w) / 6];
  const y = (r: number | null) => (r == null ? outY : top + (r - 1) * rowH);
  const path = (rs: (number | null)[]) => {
    let d = `M${xs[0]},${y(rs[0])}`;
    for (let i = 1; i < 3; i++) {
      const x0 = xs[i - 1], x1 = xs[i], mx = (x0 + x1) / 2;
      d += ` C${mx},${y(rs[i - 1])} ${mx},${y(rs[i])} ${x1},${y(rs[i])}`;
    }
    return d;
  };
  const hl = lines.find((l) => l.id === hot);

  return (
    <figure className="panel hidden overflow-hidden px-0 pt-3 pb-2 lg:block" aria-label="How the same advisories rank in each leg" data-testid="rank-flow">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4">
        <span className="text-sm font-semibold">How the fusion reorders them</span>
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2">
          <Key color="#009aa6" label={`in both legs' top ${k}`} />
          <Key color="#9aa1a4" label="found by one leg" />
          <Key color="#9aa1a4" dashed label={`outside that leg's top ${k}`} />
        </span>
      </figcaption>
      <div ref={box} className="relative">
        <svg width={w} height={H} className="block" role="img"
          aria-label={`Rank of each advisory in the keyword, vector and hybrid lists; ${lines.filter((l) => l.both).length} of ${lines.length} are in both legs' top ${k}.`}
          onMouseLeave={() => onHot(null)}>
          <rect x={0} y={outY - laneGap / 2 - 2} width={w} height={laneGap + 4} fill="#e9eef0" opacity={0.55} />
          {xs.map((x, i) => (
            <g key={i}>
              <line x1={x} x2={x} y1={top - 6} y2={y(k) + 6} stroke="#c4c8ca" />
              {[1, k].map((r) => <text key={r} x={x - 8} y={y(r)} dy="0.32em" textAnchor="end" className="fill-mute font-mono text-[10px]">{r}</text>)}
            </g>
          ))}
          <text x={8} y={outY} dy="0.32em" className="fill-mute text-[10px]">outside top {k}</text>
          {lines.map((l) => {
            const isHot = hot === l.id;
            return (
              <path key={l.id} d={path(l.rs)} fill="none"
                stroke={isHot ? "#00757f" : l.both ? "#009aa6" : "#9aa1a4"}
                strokeWidth={isHot ? 3 : l.both ? 1.8 : 1.2}
                strokeOpacity={hot && !isHot ? 0.18 : l.both ? 0.85 : 0.5}
                strokeDasharray={!isHot && l.rs.some((r) => r == null) ? "4 3" : undefined}
                onMouseEnter={() => onHot(l.id)} style={{ cursor: "pointer" }} />
            );
          })}
          {lines.map((l) => l.rs.map((r, i) => r != null && (
            <circle key={`${l.id}-${i}`} cx={xs[i]} cy={y(r)} r={hot === l.id ? 4.5 : 2.6}
              fill={hot === l.id ? "#00757f" : l.both ? "#009aa6" : "#9aa1a4"} stroke="#fbfcfd" strokeWidth={1.5}
              opacity={hot && hot !== l.id ? 0.25 : 1} onMouseEnter={() => onHot(l.id)} />
          )))}
          {/* wide invisible hit paths so thin lines are easy to hover */}
          {lines.map((l) => <path key={`hit-${l.id}`} d={path(l.rs)} fill="none" stroke="transparent" strokeWidth={10} onMouseEnter={() => onHot(l.id)} />)}
        </svg>
        {hl && (
          <div className="pointer-events-none absolute top-1 left-1/2 -translate-x-1/2 rounded-[6px] border border-hair bg-paper px-3 py-1.5 font-mono text-xs shadow-[0_2px_8px_rgba(16,18,19,.08)]">
            <span className="font-semibold text-ink">{hl.id}</span>
            <span className="ml-3 text-mute">KW {hl.rs[0] ?? "–"} · VEC {hl.rs[1] ?? "–"} · hybrid {hl.rs[2] ?? "–"}</span>
          </div>
        )}
      </div>
    </figure>
  );
}

function Key({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="20" height="8" aria-hidden><line x1="1" x2="19" y1="4" y2="4" stroke={color} strokeWidth="2" strokeDasharray={dashed ? "4 3" : undefined} /></svg>
      {label}
    </span>
  );
}
