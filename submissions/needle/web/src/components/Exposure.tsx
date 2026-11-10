import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fmt, type ExposureRow, type Status, type TriageResult } from "../api";
import { StatusLabel } from "./ui";

const ORDER: Status[] = ["AFFECTED", "NOT_CONFIRMED", "UNKNOWN_COVERAGE", "PREVIOUSLY_AFFECTED"];
const MEANS: Record<Status, string> = {
  AFFECTED: "The deployed version is listed by the advisory: an exact package and version match in NEEDLE.ADV_AFFECTED.",
  NOT_CONFIRMED: "The service deploys the package, but the deployed version is not listed. The advisory may use ranges, or the data may be incomplete. It is not a clean bill of health.",
  UNKNOWN_COVERAGE: "The advisory names a package the service deploys, but OSV gives only version ranges for it, with no enumerated versions. Not checked.",
  PREVIOUSLY_AFFECTED: "An earlier, now-ended run of listed versions in the deploy history.",
};

/* One line per service + package + version (+ window for past exposure); the advisories that hit it are listed
   together, so the tab counts and the verdict slab both count services. */
interface Group {
  key: string; service: string; team: string; pkg: string; version: string | null; since: string | null;
  until: string | null; days: number | null; versions: string | null; ids: string[];
}
function group(rows: ExposureRow[], status: Status): Group[] {
  const m = new Map<string, Group>();
  for (const r of rows) {
    const key = [r.SERVICE, r.PACKAGE, r.VERSION_NOW, status === "PREVIOUSLY_AFFECTED" ? `${r.EXPOSED_SINCE}|${r.EXPOSED_UNTIL}` : ""].join("|");
    const g = m.get(key) ?? { key, service: r.SERVICE, team: r.OWNER_TEAM, pkg: r.PACKAGE, version: r.VERSION_NOW, since: r.EXPOSED_SINCE,
      until: r.EXPOSED_UNTIL, days: r.DAYS_EXPOSED, versions: r.VERSIONS, ids: [] };
    if (r.EXPOSED_SINCE && (!g.since || r.EXPOSED_SINCE < g.since)) g.since = r.EXPOSED_SINCE;
    if (r.DAYS_EXPOSED != null && (g.days == null || r.DAYS_EXPOSED > g.days)) g.days = r.DAYS_EXPOSED;
    if (!g.ids.includes(r.ADV_ID)) g.ids.push(r.ADV_ID);
    m.set(key, g);
  }
  const list = [...m.values()];
  return status === "AFFECTED" ? list.sort((a, b) => (b.days ?? 0) - (a.days ?? 0))
    : status === "PREVIOUSLY_AFFECTED" ? list.sort((a, b) => String(a.since).localeCompare(String(b.since)))
      : list.sort((a, b) => a.service.localeCompare(b.service));
}

export default function Exposure({ result, modeIds }: { result: TriageResult; modeIds: Set<string> }) {
  const rows = useMemo(() => result.exposure.filter((r) => modeIds.has(r.ADV_ID)), [result, modeIds]);
  const counts = useMemo(() => Object.fromEntries(ORDER.map((s) => [s, new Set(rows.filter((r) => r.STATUS === s).map((r) => r.SERVICE)).size])) as Record<Status, number>, [rows]);
  const [tab, setTab] = useState<Status>(() => ORDER.find((s) => counts[s] > 0) ?? "AFFECTED");
  if (result.exposure_error) return null;
  const shown = group(rows.filter((r) => r.STATUS === tab), tab);
  const dated = tab === "AFFECTED" || tab === "PREVIOUSLY_AFFECTED";

  return (
    <section aria-label="Affected services" className="panel overflow-hidden">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2 px-4 pt-4 sm:px-5">
        <div>
          <h2 className="text-lg font-semibold tracking-[-0.01em]">Services and since when</h2>
          <p className="mt-0.5 text-sm text-mute">
            <code className="font-mono text-[13px] text-ink-2">SBOM_COMPONENT FOR BUSINESS_TIME AS OF CURRENT DATE</code>, joined to the deploy history.
          </p>
        </div>
        <span className="rounded-[3px] border border-amber/40 bg-amber-wash px-1.5 py-[1px] font-mono text-[11px] font-semibold text-amber">SYNTHETIC FLEET · real PyPI versions</span>
      </div>
      <ExposureTimeline rows={rows} />
      <div role="tablist" aria-label="Exposure status, services per status" className="mt-3 flex gap-1 overflow-x-auto border-b border-hair px-3 sm:px-4">
        {ORDER.map((s) => (
          <button key={s} role="tab" aria-selected={tab === s} onClick={() => setTab(s)}
            className="relative flex shrink-0 items-center gap-2 px-2 py-2.5 whitespace-nowrap">
            <StatusLabel status={s} />
            <span className={`font-mono text-xs num ${tab === s ? "font-semibold text-ink" : "text-mute"}`}>{counts[s]}</span>
            {tab === s && <span className="absolute inset-x-2 bottom-0 h-[2px] bg-ink" />}
          </button>
        ))}
      </div>
      <p className="px-4 pt-3 text-xs text-mute sm:px-5">{MEANS[tab]}</p>
      {shown.length === 0 ? (
        <p className="px-4 py-6 text-sm text-mute sm:px-5">
          {tab === "AFFECTED"
            ? "No exact package and version match for the ranked advisories. That is not a clean bill of health: see NOT_CONFIRMED."
            : `No ${tab} services for these advisories.`}
        </p>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead>
              <tr className="border-y border-hair bg-surface/60 text-left text-xs text-mute">
                <Th>Service</Th><Th>Team</Th><Th>Package</Th><Th>Version now</Th><Th>Advisories</Th>
                {dated && <><Th>Exposed since</Th>{tab === "PREVIOUSLY_AFFECTED" && <Th>Fixed on</Th>}<Th right>Days</Th><Th>Listed versions in window</Th></>}
              </tr>
            </thead>
            <tbody>
              {shown.map((g) => (
                <tr key={g.key} className="border-b border-hair last:border-b-0 hover:bg-ground">
                  <Td className="font-semibold">{g.service}</Td>
                  <Td className="text-mute">{g.team}</Td>
                  <Td mono>{g.pkg}</Td>
                  <Td mono>{g.version ?? "–"}</Td>
                  <Td mono className="whitespace-normal">
                    <span className="flex max-w-[22rem] flex-wrap gap-x-3 gap-y-0.5">
                      {g.ids.map((id) => <a key={id} href={`https://osv.dev/vulnerability/${id}`} target="_blank" rel="noreferrer noopener">{id}</a>)}
                    </span>
                  </Td>
                  {dated && <>
                    <Td mono>{g.since?.slice(0, 10) ?? "–"}</Td>
                    {tab === "PREVIOUSLY_AFFECTED" && <Td mono>{g.until?.slice(0, 10) ?? "–"}</Td>}
                    <Td mono right className={tab === "AFFECTED" ? "font-semibold text-affected" : ""}>{fmt.int(g.days)}</Td>
                    <Td mono className="text-mute">{g.versions ?? "–"}</Td>
                  </>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Th({ children, right }: { children: ReactNode; right?: boolean }) {
  return <th className={`px-4 py-2 font-medium whitespace-nowrap first:pl-4 sm:first:pl-5 ${right ? "text-right" : ""}`}>{children}</th>;
}
function Td({ children, mono, right, className = "" }: { children: ReactNode; mono?: boolean; right?: boolean; className?: string }) {
  return <td className={`px-4 py-2 align-top whitespace-nowrap first:pl-4 sm:first:pl-5 ${mono ? "font-mono text-[13px] num" : ""} ${right ? "text-right" : ""} ${className}`}>{children}</td>;
}

/* Exposure over time: one bar per service window from the temporal SBOM join. AFFECTED runs from "exposed since"
   to today (since + DAYS_EXPOSED); PREVIOUSLY_AFFECTED from since to "fixed on". Status is also written, not
   carried by colour alone. */
function ExposureTimeline({ rows }: { rows: ExposureRow[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(900);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const day = 86400000;
  const bars = useMemo(() => {
    const out: { key: string; service: string; pkg: string; status: Status; from: number; to: number; days: number }[] = [];
    for (const st of ["AFFECTED", "PREVIOUSLY_AFFECTED"] as Status[]) {
      for (const g of group(rows.filter((r) => r.STATUS === st), st)) {
        if (!g.since) continue;
        const from = Date.parse(g.since.slice(0, 10));
        const to = st === "AFFECTED" ? from + (g.days ?? 0) * day : g.until ? Date.parse(g.until.slice(0, 10)) : from + (g.days ?? 0) * day;
        out.push({ key: g.key, service: g.service, pkg: `${g.pkg}${g.version ? "==" + g.version : ""}`, status: st, from, to, days: g.days ?? 0 });
      }
    }
    return out.sort((a, b) => a.from - b.from);
  }, [rows]);
  if (!bars.length) return null;
  const today = Math.max(...bars.filter((b) => b.status === "AFFECTED").map((b) => b.to), ...bars.map((b) => b.to));
  const start = Math.min(...bars.map((b) => b.from)) - 60 * day;
  const L = Math.min(260, w * 0.32), R = 92, rowH = 24, top = 8, axis = 26;
  const H = top + bars.length * rowH + axis;
  const x = (t: number) => L + ((t - start) / (today - start)) * (w - L - R);
  const years: number[] = [];
  for (let yv = new Date(start).getUTCFullYear() + 1; yv <= new Date(today).getUTCFullYear(); yv++) years.push(yv);
  return (
    <figure className="mx-4 mt-4 sm:mx-5" data-testid="exposure-timeline" aria-label="Exposure windows per service">
      <figcaption className="mb-1 flex flex-wrap items-baseline justify-between gap-2 text-xs text-mute">
        <span className="text-sm font-semibold text-ink">Exposure over time</span>
        <span className="flex items-center gap-4">
          <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded-sm bg-affected" />AFFECTED, still running</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded-sm bg-[#9aa1a4]" />previously affected, ended</span>
        </span>
      </figcaption>
      <div ref={box}>
        <svg width={w} height={H} className="block" role="img"
          aria-label={bars.map((b) => `${b.service} ${b.pkg}: ${b.status === "AFFECTED" ? "affected" : "previously affected"} for ${b.days} days`).join("; ")}>
          {years.map((yv) => {
            const xx = x(Date.UTC(yv, 0, 1));
            return (
              <g key={yv}>
                <line x1={xx} x2={xx} y1={top - 4} y2={H - axis + 4} stroke="#dde3e5" />
                <text x={xx} y={H - 8} textAnchor="middle" className="fill-mute font-mono text-[10px]">{yv}</text>
              </g>
            );
          })}
          <line x1={x(today)} x2={x(today)} y1={top - 4} y2={H - axis + 4} stroke="#101213" strokeDasharray="3 3" />
          <text x={x(today)} y={H - 8} textAnchor="middle" className="fill-ink font-mono text-[10px] font-semibold">today</text>
          {bars.map((b, i) => {
            const yy = top + i * rowH, red = b.status === "AFFECTED";
            return (
              <g key={b.key}>
                <text x={0} y={yy + rowH / 2} dy="0.32em" className="fill-ink text-[12px] font-semibold">{b.service}</text>
                <text x={L - 10} y={yy + rowH / 2} dy="0.32em" textAnchor="end" className="fill-mute font-mono text-[10.5px]">{b.pkg}</text>
                <rect x={x(b.from)} y={yy + 6} width={Math.max(3, x(b.to) - x(b.from))} height={rowH - 12} rx={3}
                  fill={red ? "#c4251c" : "#9aa1a4"} opacity={red ? 0.92 : 0.75} />
                <text x={x(b.to) + 8} y={yy + rowH / 2} dy="0.32em" className={`font-mono text-[11px] ${red ? "fill-affected font-semibold" : "fill-mute"}`}>
                  {b.days.toLocaleString("en-US")} d{red ? "" : ", ended"}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </figure>
  );
}
