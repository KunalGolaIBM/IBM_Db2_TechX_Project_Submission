import clsx from 'clsx';
import { motion } from 'motion/react';
import { ArrowRight, CheckCircle2, GitCompareArrows, MinusCircle, PlusCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import CountUp from '@/components/reactbits/CountUp';
import { Button, Card, CardHeader, ErrorNote, GateBadge, PageHeader, SeverityBadge } from '@/components/ui';
import { api, type AssessmentRow, type FindingRow } from '@/lib/api';
import { dateTime } from '@/lib/format';
import { useApi } from '@/lib/hooks';

interface Diff {
  new_count: number;
  resolved_count: number;
  unchanged_count: number;
  new_findings: FindingRow[];
  resolved_findings: FindingRow[];
  unchanged_findings: FindingRow[];
}

const COLS = [
  { key: 'resolved', title: 'Resolved', icon: CheckCircle2, color: '#42d392', empty: 'Nothing was fixed between these runs.' },
  { key: 'new', title: 'New', icon: PlusCircle, color: '#ff5c66', empty: 'No new issues introduced.' },
  { key: 'unchanged', title: 'Still open', icon: MinusCircle, color: '#94a1bb', empty: 'No issues carried over.' },
] as const;

function Picker({ label, value, onChange, items }: { label: string; value: string; onChange: (v: string) => void; items: AssessmentRow[] }) {
  return (
    <label className="block flex-1">
      <span className="text-xs font-medium uppercase tracking-wider text-faint">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="mt-2 h-11 w-full rounded-xl bg-ink-950/60 px-3 text-sm outline-none ring-1 ring-line focus:ring-brand-400/60">
        <option value="">Select an assessment…</option>
        {items.map((a) => (
          <option key={a.ASSESSMENT_ID} value={a.ASSESSMENT_ID}>
            {a.PROJECT_NAME} · {a.STATUS} · {dateTime(a.STARTED_AT)}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function Compare() {
  const [params, setParams] = useSearchParams();
  const list = useApi<{ items: AssessmentRow[] }>('/api/assessments?limit=200');
  const [prev, setPrev] = useState(params.get('previous') ?? '');
  const [curr, setCurr] = useState(params.get('current') ?? '');
  const [diff, setDiff] = useState<Diff | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const byId = useMemo(() => new Map((list.data?.items ?? []).map((a) => [a.ASSESSMENT_ID, a])), [list.data]);

  async function run(p = prev, c = curr) {
    if (!p || !c) return;
    setBusy(true);
    setError(null);
    try {
      setDiff(await api<Diff>(`/api/compare?previous=${encodeURIComponent(p)}&current=${encodeURIComponent(c)}`));
      setParams({ previous: p, current: c }, { replace: true });
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (prev && curr) run(prev, curr);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pa = byId.get(prev);
  const ca = byId.get(curr);

  return (
    <div>
      <PageHeader eyebrow="Regression tracking" title="Compare two runs"
        description="Findings keep a stable SHA-256 fingerprint across runs, so ShipSafe can tell exactly what was fixed, what is new, and what is still open. The diff is saved to Db2 ASSESSMENT_DIFFS." />
      <Card className="p-5">
        <div className="flex flex-wrap items-end gap-4">
          <Picker label="Before" value={prev} onChange={setPrev} items={list.data?.items ?? []} />
          <ArrowRight className="mb-3 hidden size-5 text-faint sm:block" />
          <Picker label="After" value={curr} onChange={setCurr} items={list.data?.items ?? []} />
          <Button variant="primary" size="lg" onClick={() => run()} loading={busy} disabled={!prev || !curr || prev === curr}
            icon={<GitCompareArrows className="size-4" />}>Compare</Button>
        </div>
      </Card>
      <div className="mt-4"><ErrorNote error={error} /></div>

      {diff && pa && ca && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-6">
          <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-center">
            {[pa, ca].map((a, i) => (
              <Card key={a.ASSESSMENT_ID} className={clsx('p-5', i === 1 && 'md:order-3')}>
                <div className="text-xs uppercase tracking-wider text-faint">{i === 0 ? 'Before' : 'After'}</div>
                <div className="mt-2 flex items-center justify-between gap-3">
                  <div className="font-medium">{a.PROJECT_NAME}</div><GateBadge gate={a.STATUS} />
                </div>
                <div className="mono mt-1 text-xs text-faint">{a.ASSESSMENT_ID} · {dateTime(a.STARTED_AT)}</div>
              </Card>
            ))}
            <div className="grid place-items-center md:order-2"><ArrowRight className="size-6 text-brand-400" /></div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            {COLS.map((c) => {
              const items = diff[`${c.key}_findings` as 'new_findings'];
              return (
                <Card key={c.key}>
                  <CardHeader title={c.title} icon={<c.icon className="size-4" style={{ color: c.color }} />}
                    action={<span className="text-3xl font-semibold" style={{ color: c.color }}><CountUp to={items.length} duration={0.8} /></span>} />
                  <div className="space-y-2 p-4">
                    {items.length === 0 && <p className="px-2 py-6 text-center text-sm text-muted">{c.empty}</p>}
                    {items.map((f, i) => (
                      <motion.div key={f.FINGERPRINT} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                        className="rounded-xl bg-white/[0.03] p-3 ring-1 ring-line">
                        <SeverityBadge severity={f.SEVERITY} />
                        <div className={clsx('mt-1.5 text-sm', c.key === 'resolved' && 'text-muted line-through decoration-ok/60')}>{f.TITLE}</div>
                        <div className="mono mt-1 text-[11px] text-faint">{f.FILE_PATH}{f.LINE_START ? `:${f.LINE_START}` : ''}</div>
                      </motion.div>
                    ))}
                  </div>
                </Card>
              );
            })}
          </div>
        </motion.div>
      )}
    </div>
  );
}
