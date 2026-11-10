import { fmt, type ExposureRow, type Mode, type TriageResult } from "../api";
import { StatusLabel } from "./ui";

/* The one strong panel: the answer to "which services does this hit?", from the SQL exposure rows only. */
export default function Verdict({ result, modeIds, mode }: { result: TriageResult; modeIds: Set<string>; mode: Mode }) {
  if (result.exposure_error) {
    const noGrant = result.exposure_error.kind === "no_grant";
    return (
      <section aria-label="Exposure verdict" className="rounded-[6px] bg-slab p-5 text-paper sm:p-6">
        <p className="text-lg font-semibold">{noGrant ? `Exposure is not granted to ${result.user}` : "Exposure query failed"}</p>
        <p className="mt-1 max-w-[80ch] text-sm text-slab-mute">
          {noGrant
            ? "This identity may rank advisories but has no SELECT on the affected-version or SBOM tables. The rankings below still come from Db2 under row access control."
            : result.exposure_error.message}
        </p>
      </section>
    );
  }
  const rows = result.exposure.filter((r) => modeIds.has(r.ADV_ID));
  const by = (s: string) => rows.filter((r) => r.STATUS === s);
  const services = (rs: ExposureRow[]) => new Set(rs.map((r) => r.SERVICE)).size;
  const aff = by("AFFECTED");
  const groups = groupAffected(aff);
  const longest = aff.length ? Math.max(...aff.map((r) => r.DAYS_EXPOSED ?? 0)) : null;
  const n = services(aff);

  return (
    <section aria-label="Exposure verdict" data-testid="verdict" className="overflow-hidden rounded-[6px] bg-slab text-paper">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_auto]">
        <div className="min-w-0 p-5 sm:p-6">
          <p className="flex items-baseline gap-3">
            <span className={`font-mono text-4xl font-semibold num ${n ? "text-affected-ink" : "text-paper"}`}>{n}</span>
            <span className="text-xl font-semibold tracking-[-0.01em]">{n === 1 ? "service affected now" : "services affected now"}</span>
          </p>
          {groups.length ? (
            <ul className="mt-3 grid gap-1.5">
              {groups.map((g) => (
                <li key={`${g.service}-${g.pkg}-${g.version}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                  <StatusLabel status="AFFECTED" />
                  <span className="font-semibold">{g.service}</span>
                  <span className="font-mono text-[13px] text-slab-mute">{g.pkg}=={g.version}</span>
                  <span className="text-slab-mute">since <span className="font-mono text-paper num">{g.since}</span> · <span className="font-mono text-paper num">{fmt.int(g.days)}</span> days · {g.advs} {g.advs === 1 ? "advisory" : "advisories"}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 max-w-[70ch] text-sm text-slab-mute">
              No exact package and version match for these advisories. That is not a clean bill of health: read the
              NOT_CONFIRMED and UNKNOWN_COVERAGE rows below.
            </p>
          )}
        </div>
        <dl className="grid grid-cols-2 border-t border-slab-rule sm:grid-cols-4 lg:border-t-0 lg:border-l">
          <Kpi label="longest exposure, days" value={longest == null ? "–" : fmt.int(longest)} tone={longest ? "red" : undefined} />
          <Kpi label="not confirmed" value={services(by("NOT_CONFIRMED"))} status="NOT_CONFIRMED" />
          <Kpi label="unknown coverage" value={services(by("UNKNOWN_COVERAGE"))} status="UNKNOWN_COVERAGE" />
          <Kpi label="previously affected" value={services(by("PREVIOUSLY_AFFECTED"))} status="PREVIOUSLY_AFFECTED" />
        </dl>
      </div>
      <p className="border-t border-slab-rule px-5 py-2.5 text-xs text-slab-mute sm:px-6">
        <span className="mr-2 rounded-[3px] border border-amber-ink/60 px-1.5 py-[1px] font-mono text-[11px] font-semibold text-amber-ink">SYNTHETIC FLEET</span>
        Fictional services, real PyPI versions. Counts are services, from the top {modeIds.size} {mode} advisories. AFFECTED
        means an exact package and version match; every other status still needs a person to look.
      </p>
    </section>
  );
}

function Kpi({ label, value, tone, status }: { label: string; value: number | string; tone?: "red"; status?: "NOT_CONFIRMED" | "UNKNOWN_COVERAGE" | "PREVIOUSLY_AFFECTED" }) {
  const color = tone === "red" ? "text-affected-ink" : status === "UNKNOWN_COVERAGE" && value ? "text-amber-ink" : "text-paper";
  return (
    <div className="flex min-w-[9.5rem] flex-col justify-between gap-2 border-slab-rule px-5 py-4 odd:border-r sm:border-r sm:last:border-r-0 lg:py-6">
      <dd className={`font-mono text-2xl font-semibold num ${color}`}>{value}</dd>
      <dt className="text-xs text-slab-mute">{status ? <StatusLabel status={status} onInk /> : label}</dt>
    </div>
  );
}

function groupAffected(rows: ExposureRow[]) {
  const m = new Map<string, { service: string; pkg: string; version: string; since: string; days: number; ids: Set<string> }>();
  for (const r of rows) {
    const key = `${r.SERVICE}|${r.PACKAGE}|${r.VERSION_NOW}`;
    const g = m.get(key) ?? { service: r.SERVICE, pkg: r.PACKAGE, version: r.VERSION_NOW ?? "", since: r.EXPOSED_SINCE ?? "", days: 0, ids: new Set<string>() };
    if (r.EXPOSED_SINCE && (!g.since || r.EXPOSED_SINCE < g.since)) g.since = r.EXPOSED_SINCE;
    g.days = Math.max(g.days, r.DAYS_EXPOSED ?? 0);
    g.ids.add(r.ADV_ID);
    m.set(key, g);
  }
  return [...m.values()].sort((a, b) => b.days - a.days).map((g) => ({ ...g, since: g.since.slice(0, 10), advs: g.ids.size }));
}
