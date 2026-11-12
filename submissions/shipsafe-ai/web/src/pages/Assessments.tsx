import clsx from 'clsx';
import { motion } from 'motion/react';
import { Activity, ArrowUpRight, Radar, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Card, EmptyState, ErrorNote, GateBadge, PageHeader, Skeleton } from '@/components/ui';
import type { AssessmentRow, Gate } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { SEV_COLOR, dateTime, riskScore } from '@/lib/format';
import { useApi } from '@/lib/hooks';

export default function Assessments() {
  const { can } = useAuth();
  const { data, loading, error } = useApi<{ items: AssessmentRow[] }>('/api/assessments?limit=200', 30000);
  const [gate, setGate] = useState<Gate | 'all'>('all');
  const [q, setQ] = useState('');
  const rows = useMemo(() => (data?.items ?? []).filter((a) =>
    (gate === 'all' || a.STATUS === gate) && (!q || `${a.PROJECT_NAME} ${a.ASSESSMENT_ID}`.toLowerCase().includes(q.toLowerCase()))), [data, gate, q]);

  return (
    <div>
      <PageHeader eyebrow="History" title="Assessments" description="Every scan ever run, read straight from the Db2 ASSESSMENTS table."
        actions={can('operator') && <Link to="/scan"><Button variant="primary" icon={<Radar className="size-4" />}>New scan</Button></Link>} />
      <ErrorNote error={error} />
      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-4">
          {(['all', 'BLOCKED', 'PASS_WITH_WARNINGS', 'PASS'] as const).map((g) => (
            <button key={g} onClick={() => setGate(g)}
              className={clsx('focus-ring rounded-full px-3 py-1 text-xs ring-1 transition', gate === g ? 'bg-white/[0.1] text-fg ring-line-strong' : 'text-muted ring-line hover:text-fg')}>
              {g === 'all' ? 'All' : g === 'PASS_WITH_WARNINGS' ? 'Warnings' : g[0] + g.slice(1).toLowerCase()}
            </button>
          ))}
          <div className="ml-auto flex h-9 items-center gap-2 rounded-xl bg-ink-950/50 px-3 ring-1 ring-line">
            <Search className="size-4 text-faint" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Project or ID" className="w-44 bg-transparent text-sm outline-none placeholder:text-faint" />
          </div>
        </div>
        {loading && !data && <div className="space-y-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>}
        {data && data.items.length === 0 && (
          <EmptyState icon={<Activity className="size-6" />} title="Nothing here yet" body="Run a scan and it will appear here, stored in IBM Db2." />
        )}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            {rows.length > 0 && (
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-faint">
                  <th className="px-5 py-3 font-medium">Gate</th><th className="px-3 py-3 font-medium">Project</th>
                  <th className="px-3 py-3 font-medium">Findings</th><th className="px-3 py-3 font-medium">Risk</th>
                  <th className="px-3 py-3 font-medium">Profile</th><th className="px-3 py-3 font-medium">When</th><th />
                </tr>
              </thead>
            )}
            <tbody>
              {rows.map((a, i) => (
                <motion.tr key={a.ASSESSMENT_ID} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(i, 12) * 0.02 }}
                  className="group border-t border-line transition hover:bg-white/[0.025]">
                  <td className="px-5 py-3.5"><GateBadge gate={a.STATUS} /></td>
                  <td className="px-3 py-3.5">
                    <Link to={`/assessments/${a.ASSESSMENT_ID}`} className="font-medium hover:text-brand-300">{a.PROJECT_NAME}</Link>
                    <div className="mono text-[11px] text-faint">{a.ASSESSMENT_ID}</div>
                  </td>
                  <td className="px-3 py-3.5">
                    <div className="flex items-center gap-1.5">
                      {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((k) => {
                        const n = a[`${k}_COUNT` as 'CRITICAL_COUNT'];
                        return n ? (
                          <span key={k} className="mono rounded-md px-1.5 py-0.5 text-[11px] font-medium"
                            style={{ color: SEV_COLOR[k.toLowerCase() as 'critical'], background: `${SEV_COLOR[k.toLowerCase() as 'critical']}18` }}>
                            {n}{k[0]}
                          </span>
                        ) : null;
                      })}
                      {a.FINDINGS_COUNT === 0 && <span className="text-xs text-ok">clean</span>}
                    </div>
                  </td>
                  <td className="mono px-3 py-3.5">{riskScore(a.CRITICAL_COUNT, a.HIGH_COUNT, a.MEDIUM_COUNT, a.LOW_COUNT)}</td>
                  <td className="mono px-3 py-3.5 text-xs text-muted">{a.PROFILE}</td>
                  <td className="px-3 py-3.5 text-xs text-muted">{dateTime(a.STARTED_AT)}</td>
                  <td className="px-4"><Link to={`/assessments/${a.ASSESSMENT_ID}`}><ArrowUpRight className="size-4 text-faint opacity-0 transition group-hover:opacity-100" /></Link></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
