import clsx from 'clsx';
import { AnimatePresence, motion } from 'motion/react';
import {
  BookMarked, Check, ChevronDown, CircleDashed, Copy, Database, Download, ExternalLink, FileCode2, GitCompareArrows, Package, Search, ShieldAlert, X,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Line, LineChart, ResponsiveContainer, Tooltip } from 'recharts';
import { toast } from 'sonner';
import SpotlightCard from '@/components/reactbits/SpotlightCard';
import { Button, Card, CardHeader, EmptyState, ErrorNote, GateBadge, SeverityBadge, Skeleton } from '@/components/ui';
import { download, type AssessmentRow, type FindingRow, type Severity, type ToolRunRow, type TrendRow } from '@/lib/api';
import { GATE_META, SEVERITIES, SEV_COLOR, dateTime, duration, riskScore } from '@/lib/format';
import { useApi } from '@/lib/hooks';

interface Detail {
  assessment: AssessmentRow;
  findings: FindingRow[];
  tool_runs: ToolRunRow[];
  dependencies: { PACKAGE_NAME: string; VERSION: string; MANIFEST_PATH: string; ECOSYSTEM: string }[];
  history: TrendRow[];
}

function FindingCard({ f, open, onToggle }: { f: FindingRow; open: boolean; onToggle: () => void }) {
  const policy = f.EVIDENCE?.policy;
  const sources = (f.EVIDENCE?.sources as string[] | undefined) ?? [f.SOURCE_TOOL];
  const links = f.REFERENCES.filter((r) => r.startsWith('http'));
  return (
    <motion.div layout className={clsx('overflow-hidden rounded-2xl ring-1 transition-colors', open ? 'bg-white/[0.04] ring-line-strong' : 'bg-white/[0.02] ring-line hover:bg-white/[0.035]')}>
      <button onClick={onToggle} className="focus-ring flex w-full items-start gap-4 p-4 text-left">
        <span className="mt-1 h-10 w-1 shrink-0 rounded-full" style={{ background: SEV_COLOR[f.SEVERITY] }} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={f.SEVERITY} />
            <span className="mono text-[11px] text-faint">{f.RULE_ID}</span>
            {sources.map((s) => <span key={s} className="mono rounded bg-white/[0.05] px-1.5 py-0.5 text-[10px] text-muted">{s}</span>)}
          </div>
          <div className="mt-1.5 font-medium leading-snug">{f.TITLE}</div>
          <div className="mono mt-1 flex items-center gap-1.5 text-xs text-muted">
            <FileCode2 className="size-3.5" />{f.FILE_PATH ? `${f.FILE_PATH}${f.LINE_START ? `:${f.LINE_START}` : ''}` : 'repository'}
            {policy && <><span className="mx-1 text-faint">·</span><BookMarked className="size-3.5 text-violet-400" /><span className="text-violet-400">{policy.doc_id}</span></>}
          </div>
        </div>
        <ChevronDown className={clsx('mt-1 size-5 shrink-0 text-faint transition-transform', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}>
            <div className="space-y-4 border-t border-line px-5 pb-5 pt-4 sm:pl-9">
              {f.DESCRIPTION && <p className="text-sm leading-relaxed text-muted">{f.DESCRIPTION}</p>}
              {f.EVIDENCE?.snippet && (
                <div>
                  <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-faint">Evidence (secrets redacted)</div>
                  <pre className="scroll-thin overflow-x-auto rounded-xl bg-ink-950/80 p-3.5 text-[12.5px] leading-relaxed text-fg ring-1 ring-line">
                    {f.LINE_START && <span className="mr-3 select-none text-faint">{f.LINE_START}</span>}{String(f.EVIDENCE.snippet)}
                  </pre>
                </div>
              )}
              {policy && (
                <div className="rounded-xl bg-violet-500/[0.07] p-4 ring-1 ring-violet-500/25">
                  <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-violet-400">
                    <Database className="size-3.5" /> Governing policy · retrieved from the IBM Db2 vector store
                  </div>
                  <div className="mt-2 font-medium">{policy.title}</div>
                  <div className="mono mt-0.5 text-xs text-muted">{policy.doc_id} v{policy.version} · section “{policy.section}”</div>
                  {typeof policy.similarity === 'number' && (
                    <div className="mt-3 flex items-center gap-3">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                        <motion.div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-brand-400"
                          initial={{ width: 0 }} animate={{ width: `${Math.min(100, Math.max(6, policy.similarity * 300))}%` }} />
                      </div>
                      <span className="mono text-[11px] text-faint">cosine {policy.similarity.toFixed(3)}</span>
                    </div>
                  )}
                </div>
              )}
              {f.REMEDIATION && (
                <div className="flex items-start gap-3 rounded-xl bg-ok/[0.06] p-4 ring-1 ring-ok/20">
                  <Check className="mt-0.5 size-4 shrink-0 text-ok" />
                  <div className="flex-1 text-sm leading-relaxed">{f.REMEDIATION}</div>
                  <button title="Copy fix" onClick={() => { navigator.clipboard.writeText(f.REMEDIATION); toast.success('Fix copied'); }}
                    className="focus-ring rounded-lg p-1.5 text-muted hover:bg-white/[0.06] hover:text-fg"><Copy className="size-4" /></button>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-faint">
                <span className="mono">fingerprint {f.FINGERPRINT.slice(0, 16)}…</span>
                <span>confidence {f.CONFIDENCE}</span>
                {links.map((l) => (
                  <a key={l} href={l} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-brand-400 hover:text-brand-300">
                    {new URL(l).hostname.replace('www.', '')}<ExternalLink className="size-3" />
                  </a>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

const TOOL_ICON = { passed: Check, failed: X, skipped: CircleDashed, unsupported: CircleDashed, not_run: CircleDashed };

export default function AssessmentDetail() {
  const { id } = useParams();
  const { data, loading, error } = useApi<Detail>(`/api/assessments/${id}`);
  const [open, setOpen] = useState<string | null>(null);
  const [sev, setSev] = useState<Severity | 'all'>('all');
  const [q, setQ] = useState('');

  const findings = useMemo(() => (data?.findings ?? []).filter((f) =>
    (sev === 'all' || f.SEVERITY === sev) &&
    (!q || `${f.TITLE} ${f.FILE_PATH} ${f.RULE_ID}`.toLowerCase().includes(q.toLowerCase()))), [data, sev, q]);

  if (loading && !data) return <div className="space-y-4"><Skeleton className="h-44" /><Skeleton className="h-96" /></div>;
  if (error) return <ErrorNote error={error} />;
  if (!data) return null;
  const a = data.assessment;
  const meta = GATE_META[a.STATUS];
  const previous = [...data.history].reverse().find((h) => h.STARTED_AT < a.STARTED_AT);
  const exp = (format: string, ext: string) =>
    download(`/api/assessments/${a.ASSESSMENT_ID}/report?format=${format}`, `shipsafe-${a.ASSESSMENT_ID}.${ext}`).catch((e) => toast.error(e.message));

  return (
    <div className="space-y-6">
      <div className="relative overflow-hidden rounded-3xl border border-line p-7 sm:p-9" style={{ background: `linear-gradient(135deg, ${meta.color}1c, transparent 55%), #0a1020` }}>
        <div className="pointer-events-none absolute inset-0" style={{ background: `radial-gradient(520px 280px at 95% 0%, ${meta.color}30, transparent 70%)` }} />
        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <Link to="/assessments" className="text-sm text-muted hover:text-fg">← Assessments</Link>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{a.PROJECT_NAME}</h1>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <GateBadge gate={a.STATUS} size="lg" />
              <span className="text-sm text-muted">{a.GATE_REASON}</span>
            </div>
            <div className="mono mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-faint">
              <span>{a.ASSESSMENT_ID}</span><span>profile {a.PROFILE}</span><span>commit {a.COMMIT_SHA}</span><span>{dateTime(a.STARTED_AT)}</span>
              <span>{duration(a.FINISHED_AT - a.STARTED_AT)}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {previous && (
              <Link to={`/compare?previous=${previous.ASSESSMENT_ID}&current=${a.ASSESSMENT_ID}`}>
                <Button icon={<GitCompareArrows className="size-4" />}>Compare with previous</Button>
              </Link>
            )}
            <Button onClick={() => exp('markdown', 'md')} icon={<Download className="size-4" />}>Markdown</Button>
            <Button onClick={() => exp('sarif', 'sarif')} icon={<Download className="size-4" />}>SARIF</Button>
            <Button variant="ghost" onClick={() => exp('json', 'json')}>JSON</Button>
          </div>
        </div>

        <div className="relative mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          {SEVERITIES.map((s) => {
            const n = a[`${s.toUpperCase()}_COUNT` as 'CRITICAL_COUNT'];
            return (
              <button key={s} onClick={() => setSev(sev === s ? 'all' : s)}
                className={clsx('focus-ring rounded-2xl p-4 text-left ring-1 transition', sev === s ? 'bg-white/[0.08] ring-line-strong' : 'bg-ink-950/40 ring-line hover:bg-white/[0.05]')}>
                <div className="text-3xl font-semibold" style={{ color: n ? SEV_COLOR[s] : undefined }}>{n}</div>
                <div className="mt-1 text-xs capitalize text-muted">{s}</div>
              </button>
            );
          })}
          <SpotlightCard spotlightColor="rgba(165,110,255,0.2)" className="!col-span-2 !rounded-2xl !border-line !bg-ink-950/40 !p-4">
            <div className="flex items-center justify-between text-xs text-muted">
              <span>Risk score · this project</span>
              <span className="mono text-fg">{riskScore(a.CRITICAL_COUNT, a.HIGH_COUNT, a.MEDIUM_COUNT, a.LOW_COUNT)}</span>
            </div>
            <div className="mt-2 h-12">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.history}>
                  <Tooltip contentStyle={{ background: '#0a1020', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, fontSize: 11 }}
                    labelFormatter={() => ''} formatter={(v: number) => [v, 'risk']} />
                  <Line type="monotone" dataKey="RISK_SCORE" stroke="#be95ff" strokeWidth={2} dot={{ r: 2.5, fill: '#be95ff' }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </SpotlightCard>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <Card>
          <CardHeader title={`Findings (${data.findings.length})`} subtitle="Click a finding to see the evidence, the policy Db2 retrieved for it, and the fix." icon={<ShieldAlert className="size-4" />} />
          <div className="flex flex-wrap items-center gap-2 px-5 pt-4">
            {(['all', ...SEVERITIES] as const).map((s) => (
              <button key={s} onClick={() => setSev(s)}
                className={clsx('focus-ring rounded-full px-3 py-1 text-xs capitalize ring-1 transition', sev === s ? 'bg-white/[0.1] text-fg ring-line-strong' : 'text-muted ring-line hover:text-fg')}>
                {s}
              </button>
            ))}
            <div className="ml-auto flex h-8 items-center gap-2 rounded-lg bg-ink-950/50 px-2.5 ring-1 ring-line">
              <Search className="size-3.5 text-faint" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…" className="w-32 bg-transparent text-xs outline-none placeholder:text-faint" />
            </div>
          </div>
          <div className="space-y-2.5 p-5">
            {data.findings.length === 0 && (
              <EmptyState icon={<Check className="size-6" />} title="No findings" body="Every check that ran came back clean. Skipped checks are listed on the right." />
            )}
            {findings.map((f) => (
              <FindingCard key={f.FINDING_ID} f={f} open={open === f.FINDING_ID} onToggle={() => setOpen(open === f.FINDING_ID ? null : f.FINDING_ID)} />
            ))}
            {data.findings.length > 0 && findings.length === 0 && <p className="py-8 text-center text-sm text-muted">No findings match this filter.</p>}
          </div>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Checks that ran" subtitle="Provenance stored in Db2 TOOL_RUNS" icon={<Check className="size-4" />} />
            <div className="space-y-1 p-3">
              {data.tool_runs.map((t) => {
                const Icon = TOOL_ICON[t.STATUS] ?? CircleDashed;
                return (
                  <div key={t.TOOL_NAME} className="flex items-start gap-3 rounded-xl px-3 py-2.5 hover:bg-white/[0.03]">
                    <span className={clsx('mt-0.5 grid size-5 place-items-center rounded-full',
                      t.STATUS === 'passed' && 'bg-ok/15 text-ok', t.STATUS === 'failed' && 'bg-sev-critical/15 text-sev-critical',
                      !['passed', 'failed'].includes(t.STATUS) && 'bg-white/[0.06] text-faint')}>
                      <Icon className="size-3" strokeWidth={3} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="mono truncate text-[13px]">{t.TOOL_NAME}</span>
                        <span className="mono text-[11px] text-faint">{t.STATUS === 'skipped' ? 'skipped' : duration(t.DURATION_MS)}</span>
                      </div>
                      <div className="text-xs leading-snug text-muted">{t.MESSAGE}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
          <Card>
            <CardHeader title={`Dependencies (${data.dependencies.length})`} subtitle="Latest inventory for this project (Db2 DEPENDENCIES). Red = version flagged in this report." icon={<Package className="size-4" />} />
            <div className="scroll-thin max-h-72 overflow-y-auto p-3">
              {data.dependencies.length === 0 && <p className="px-3 py-4 text-sm text-muted">No pinned dependencies found.</p>}
              {data.dependencies.map((d) => {
                const flagged = data.findings.some((f) => f.CATEGORY === 'dependencies'
                  && String(f.EVIDENCE?.package ?? '').toLowerCase() === d.PACKAGE_NAME.toLowerCase()
                  && String(f.EVIDENCE?.installed_version ?? '') === d.VERSION);
                return (
                  <div key={`${d.PACKAGE_NAME}${d.MANIFEST_PATH}`} className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm">
                    <span className={clsx('size-1.5 rounded-full', flagged ? 'bg-sev-critical' : 'bg-ok')} />
                    <span className="flex-1">{d.PACKAGE_NAME}</span>
                    <span className="mono text-xs text-muted">{d.VERSION}</span>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
