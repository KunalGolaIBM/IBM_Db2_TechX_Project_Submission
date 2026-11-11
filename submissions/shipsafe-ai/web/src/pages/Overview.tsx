import { motion } from 'motion/react';
import { Activity, ArrowRight, ArrowUpRight, Boxes, FolderGit2, Radar, ShieldAlert, ShieldCheck, TrendingDown, TrendingUp } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Link } from 'react-router-dom';
import CountUp from '@/components/reactbits/CountUp';
import GradientText from '@/components/reactbits/GradientText';
import ShinyText from '@/components/reactbits/ShinyText';
import SpotlightCard from '@/components/reactbits/SpotlightCard';
import { Button, Card, CardHeader, EmptyState, ErrorNote, GateBadge, Skeleton } from '@/components/ui';
import type { Overview as OverviewData } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { SEV_COLOR, dateTime, timeAgo } from '@/lib/format';
import { useApi } from '@/lib/hooks';

function Kpi({ label, value, icon, tone, hint, i }: { label: string; value: number; icon: React.ReactNode; tone: string; hint: string; i: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i, duration: 0.45 }}>
      <SpotlightCard spotlightColor="rgba(69, 137, 255, 0.22)" className="!rounded-2xl !border-line !bg-white/[0.03] !p-5">
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-muted">{label}</span>
          <span className="grid size-8 place-items-center rounded-lg ring-1 ring-line" style={{ color: tone, background: `${tone}14` }}>{icon}</span>
        </div>
        <div className="mt-3 text-[34px] font-semibold leading-none tracking-tight" style={{ color: value > 0 && tone === SEV_COLOR.critical ? tone : undefined }}>
          <CountUp to={value} duration={1.1} separator="," />
        </div>
        <div className="mt-2 text-xs text-faint">{hint}</div>
      </SpotlightCard>
    </motion.div>
  );
}

const SERIES = ['#78a9ff', '#be95ff', '#3ddbd9', '#ff8f3d', '#f1c21b'];

interface TrendPoint { idx: number; when: number; project: string; status: OverviewData['trend'][number]['STATUS']; delta: number | null; [k: string]: unknown }

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: TrendPoint; value: number }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-ink-850 px-3.5 py-2.5 text-xs shadow-xl">
      <div className="font-medium text-fg">{r.project}</div>
      <div className="mono mt-0.5 text-faint">{dateTime(r.when)}</div>
      <div className="mt-2 flex items-center gap-3">
        <span>Risk <b className="text-fg">{payload[0].value}</b></span>
        {r.delta !== null && <span style={{ color: r.delta > 0 ? SEV_COLOR.critical : '#42d392' }}>{r.delta > 0 ? '+' : ''}{r.delta}</span>}
        <GateBadge gate={r.status} />
      </div>
    </div>
  );
}

export default function Overview() {
  const { can } = useAuth();
  const { data, loading, error } = useApi<OverviewData>('/api/overview', 20000);

  const empty = data && data.stats.assessments === 0;
  // One series per project (most recently active first), plotted over run order.
  const projects = Array.from(new Set([...(data?.trend ?? [])].reverse().map((r) => r.PROJECT_NAME))).slice(0, 5);
  const trend = (data?.trend ?? []).filter((r) => projects.includes(r.PROJECT_NAME)).map((r, i) => ({
    idx: i + 1, when: r.STARTED_AT, project: r.PROJECT_NAME, status: r.STATUS, delta: r.RISK_DELTA, [r.PROJECT_NAME]: r.RISK_SCORE,
  }));
  const bySeverity = ['critical', 'high', 'medium', 'low'].map((sev) => ({
    sev,
    total: (data?.breakdown ?? []).filter((b) => b.SEVERITY === sev).reduce((a, b) => a + Number(b.UNIQUE_ISSUES), 0),
  }));
  const categories = Array.from(new Set((data?.breakdown ?? []).map((b) => b.CATEGORY))).map((cat) => {
    const row: Record<string, number | string> = { cat };
    (data?.breakdown ?? []).filter((b) => b.CATEGORY === cat).forEach((b) => (row[b.SEVERITY] = Number(b.UNIQUE_ISSUES)));
    return row;
  });

  return (
    <div>
      <div className="relative mb-10 overflow-hidden rounded-3xl border border-line bg-gradient-to-br from-brand-600/20 via-ink-850 to-violet-500/10 p-8 sm:p-10">
        <div className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(600px 300px at 90% 0%, rgba(69,137,255,0.28), transparent 70%), radial-gradient(500px 260px at 40% 120%, rgba(165,110,255,0.22), transparent 70%)' }} />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div>
            <ShinyText text="Production readiness, live from IBM Db2" speed={3} className="mono text-xs font-medium uppercase tracking-[0.18em]" />
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-[40px]">
              {data && data.stats.open_critical > 0 ? (
                <>There {data.stats.open_critical === 1 ? 'is' : 'are'} <span className="text-sev-critical">{data.stats.open_critical} critical</span> issue{data.stats.open_critical === 1 ? '' : 's'} to fix</>
              ) : (
                <>Your projects are <GradientText colors={['#42d392', '#3ddbd9', '#78a9ff', '#42d392']} animationSpeed={7}>clear to ship</GradientText></>
              )}
            </h1>
            <p className="mt-2 max-w-xl text-muted">
              Every number here is a live query against Db2: the latest assessment per project, findings deduplicated by fingerprint, and the risk trend from a window-function view.
            </p>
          </div>
          {can('operator') && (
            <Link to="/scan"><Button variant="primary" size="lg" icon={<Radar className="size-4" />}>Run a scan</Button></Link>
          )}
        </div>
      </div>

      <ErrorNote error={error} />
      {loading && !data && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36" />)}</div>
      )}

      {empty && (
        <Card>
          <EmptyState icon={<Radar className="size-6" />} title="No assessments yet"
            body="Run your first scan. ShipSafe will check the project, store the result in IBM Db2 and fill this dashboard."
            action={can('operator') && <Link to="/scan"><Button variant="primary" icon={<ArrowRight className="size-4" />}>Start the first scan</Button></Link>} />
        </Card>
      )}

      {data && !empty && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi i={0} label="Open critical" value={data.stats.open_critical} icon={<ShieldAlert className="size-4" />} tone={SEV_COLOR.critical} hint="Latest scan of each project" />
            <Kpi i={1} label="Projects blocked" value={data.stats.projects_blocked} icon={<FolderGit2 className="size-4" />} tone={SEV_COLOR.high} hint={`of ${data.stats.projects} tracked project${data.stats.projects === 1 ? '' : 's'}`} />
            <Kpi i={2} label="Assessments in Db2" value={data.stats.assessments} icon={<Activity className="size-4" />} tone="#78a9ff" hint={`${data.stats.blocked_runs} were blocked`} />
            <Kpi i={3} label="Unique issues tracked" value={data.stats.unique_issues} icon={<Boxes className="size-4" />} tone="#be95ff" hint={`${data.stats.policy_docs} policies indexed as vectors`} />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
            <Card>
              <CardHeader title="Risk over time" subtitle="Risk = 10×critical + 5×high + 2×medium + low, per run. Change computed in Db2 with LAG() OVER." icon={<TrendingDown className="size-4" />} />
              <div className="flex flex-wrap gap-x-4 gap-y-1 px-5 pt-4">
                {projects.map((p, i) => (
                  <span key={p} className="flex items-center gap-2 text-xs text-muted">
                    <span className="h-0.5 w-4 rounded-full" style={{ background: SERIES[i] }} />{p}
                  </span>
                ))}
              </div>
              <div className="h-64 px-2 pb-4 pt-3">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trend} margin={{ left: 0, right: 16, top: 10 }}>
                    <defs>
                      {projects.map((p, i) => (
                        <linearGradient key={p} id={`risk-${i}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={SERIES[i]} stopOpacity={0.28} />
                          <stop offset="100%" stopColor={SERIES[i]} stopOpacity={0} />
                        </linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="idx" tick={{ fill: '#5f6c88', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#5f6c88', fontSize: 11 }} axisLine={false} tickLine={false} width={34} />
                    <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.15)' }} />
                    {projects.map((p, i) => (
                      <Area key={p} type="monotone" dataKey={p} stroke={SERIES[i]} strokeWidth={2.5} fill={`url(#risk-${i})`} connectNulls
                        isAnimationActive={false} dot={{ r: 3.5, fill: '#0a1020', stroke: SERIES[i], strokeWidth: 2 }} activeDot={{ r: 5 }} />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card>
              <CardHeader title="Project posture" subtitle="Latest assessment per project (Db2 view V_PROJECT_POSTURE)" icon={<FolderGit2 className="size-4" />} />
              <div className="scroll-thin mt-4 max-h-72 space-y-1 overflow-y-auto px-3 pb-4">
                {data.posture.map((p) => (
                  <Link key={p.PROJECT_ID} to={`/assessments/${p.ASSESSMENT_ID}`}
                    className="focus-ring group flex items-center gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.04]">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{p.PROJECT_NAME}</div>
                      <div className="mono text-[11px] text-faint">{timeAgo(p.STARTED_AT)} · risk {p.RISK_SCORE}</div>
                    </div>
                    {p.RISK_DELTA !== null && p.RISK_DELTA !== 0 && (
                      <span className="mono flex items-center gap-1 text-xs" style={{ color: p.RISK_DELTA > 0 ? SEV_COLOR.critical : '#42d392' }}>
                        {p.RISK_DELTA > 0 ? <TrendingUp className="size-3.5" /> : <TrendingDown className="size-3.5" />}{Math.abs(p.RISK_DELTA)}
                      </span>
                    )}
                    <GateBadge gate={p.STATUS} />
                    <ArrowUpRight className="size-4 text-faint opacity-0 transition group-hover:opacity-100" />
                  </Link>
                ))}
              </div>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_1.6fr]">
            <Card>
              <CardHeader title="Issues by severity" subtitle="Unique fingerprints across all runs" icon={<ShieldAlert className="size-4" />} />
              <div className="space-y-4 px-5 pb-6 pt-6">
                {bySeverity.map((s) => {
                  const max = Math.max(1, ...bySeverity.map((x) => x.total));
                  return (
                    <div key={s.sev}>
                      <div className="mb-1.5 flex justify-between text-sm"><span className="capitalize text-muted">{s.sev}</span><span className="mono">{s.total}</span></div>
                      <div className="h-2 overflow-hidden rounded-full bg-white/[0.05]">
                        <motion.div className="h-full rounded-full" style={{ background: SEV_COLOR[s.sev as keyof typeof SEV_COLOR] }}
                          initial={{ width: 0 }} animate={{ width: `${(s.total / max) * 100}%` }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
            <Card>
              <CardHeader title="Where issues come from" subtitle="Unique issues by category and severity (GROUP BY in Db2)" icon={<Boxes className="size-4" />} />
              <div className="h-64 px-2 pb-4 pt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categories} margin={{ left: 0, right: 16 }}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="cat" tick={{ fill: '#94a1bb', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fill: '#5f6c88', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
                    <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={{ background: '#0a1020', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, fontSize: 12 }} />
                    {(['critical', 'high', 'medium', 'low'] as const).map((s) => (
                      <Bar key={s} dataKey={s} stackId="a" fill={SEV_COLOR[s]} radius={s === "low" ? [6, 6, 0, 0] : 0} maxBarSize={44} isAnimationActive={false} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <Card>
            <CardHeader title="Recent assessments" icon={<ShieldCheck className="size-4" />}
              action={<Link to="/assessments" className="text-sm text-brand-400 hover:text-brand-300">View all</Link>} />
            <div className="mt-3 divide-y divide-line px-2 pb-2">
              {data.recent.map((a) => (
                <Link key={a.ASSESSMENT_ID} to={`/assessments/${a.ASSESSMENT_ID}`} className="focus-ring flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl px-3 py-3 transition hover:bg-white/[0.03]">
                  <GateBadge gate={a.STATUS} />
                  <span className="font-medium">{a.PROJECT_NAME}</span>
                  <span className="mono text-xs text-faint">{a.ASSESSMENT_ID}</span>
                  <span className="ml-auto flex items-center gap-3 text-xs text-muted">
                    {a.CRITICAL_COUNT > 0 && <span style={{ color: SEV_COLOR.critical }}>{a.CRITICAL_COUNT} critical</span>}
                    {a.HIGH_COUNT > 0 && <span style={{ color: SEV_COLOR.high }}>{a.HIGH_COUNT} high</span>}
                    <span>{a.FINDINGS_COUNT} findings</span>
                    <span className="text-faint">{timeAgo(a.STARTED_AT)}</span>
                  </span>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
