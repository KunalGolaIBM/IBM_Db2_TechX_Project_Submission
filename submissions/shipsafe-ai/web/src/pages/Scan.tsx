import clsx from 'clsx';
import { AnimatePresence, motion } from 'motion/react';
import { AlertTriangle, ArrowRight, Check, CircleDashed, FolderGit2, Gauge, Loader2, Radar, RotateCcw, Sparkles, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import ClickSpark from '@/components/reactbits/ClickSpark';
import DecryptedText from '@/components/reactbits/DecryptedText';
import { Button, Card, CardHeader, ErrorNote, GateBadge, PageHeader, Skeleton } from '@/components/ui';
import { api, type Job } from '@/lib/api';
import { GATE_META, SEV_COLOR } from '@/lib/format';
import { useApi } from '@/lib/hooks';

const PROFILES = [
  { id: 'quick', icon: Zap, title: 'Quick', time: '~2 s', body: 'Changed files only. Secrets and code checks, no tests.' },
  { id: 'pre-pr', icon: Gauge, title: 'Pre-PR', time: '~5 s', body: 'Recommended. Full checks plus the project’s own tests.' },
  { id: 'deep', icon: Sparkles, title: 'Deep', time: '~1 min', body: 'Adds pip-audit: every transitive dependency against OSV.' },
] as const;

const STEP_LABEL: Record<string, string> = {
  discover: 'Discover project', secrets: 'Secrets', sast: 'Code security', dependencies: 'Dependencies',
  quality: 'Code quality', tests: 'Tests', gate: 'Release gate', policies: 'Policy lookup in Db2',
  persist: 'Save to Db2', done: 'Done',
};

interface Workspace { name: string; path: string; root: string }

function Stepper({ job }: { job: Job }) {
  const seen = new Map(job.steps.map((s) => [s.key, s]));
  const keys = job.steps_total.filter((k) => seen.has(k) || job.status !== 'done');
  return (
    <ol className="relative space-y-1">
      {keys.map((key) => {
        const step = seen.get(key);
        const active = job.current_step === key && job.status === 'running';
        const done = !!step && !active;
        return (
          <motion.li key={key} layout initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
            className={clsx('flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors', active && 'bg-brand-500/10 ring-1 ring-brand-500/25')}>
            <span className={clsx('mt-0.5 grid size-5 shrink-0 place-items-center rounded-full',
              done && 'bg-ok/15 text-ok', active && 'text-brand-400', !step && 'text-faint')}>
              {done ? <Check className="size-3.5" strokeWidth={3} /> : active ? <Loader2 className="size-4 animate-spin" /> : <CircleDashed className="size-4" />}
            </span>
            <div className="min-w-0">
              <div className={clsx('text-sm font-medium', !step && 'text-faint')}>{STEP_LABEL[key] ?? key}</div>
              {step && <div className="text-xs text-muted">{step.message}</div>}
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}

export default function Scan() {
  const navigate = useNavigate();
  const ws = useApi<{ roots: string[]; items: Workspace[] }>('/api/workspaces');
  const [target, setTarget] = useState('');
  const [profile, setProfile] = useState<string>('pre-pr');
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!target && ws.data?.items.length) setTarget(ws.data.items[0].path);
  }, [ws.data, target]);

  useEffect(() => {
    if (!job || job.status === 'done' || job.status === 'failed') return;
    const id = window.setInterval(async () => {
      try {
        const next = await api<Job>(`/api/scans/${job.job_id}`);
        setJob(next);
        if (next.status === 'done') toast.success(`Scan finished: ${GATE_META[next.gate!].label}`);
        if (next.status === 'failed') toast.error('Scan failed', { description: next.error ?? undefined });
      } catch (e) {
        setError(e as Error);
      }
    }, 450);
    return () => window.clearInterval(id);
  }, [job]);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      setJob(await api<Job>('/api/scans', { method: 'POST', body: JSON.stringify({ target, profile }) }));
    } catch (e) {
      setError(e as Error);
    } finally {
      setStarting(false);
    }
  }

  const running = job && (job.status === 'queued' || job.status === 'running');
  const s = job?.summary;

  return (
    <div>
      <PageHeader eyebrow="Pre-PR assessment" title="Run a scan"
        description="Pick a project, choose how deep to look, and get a release decision in seconds. Every run is saved to IBM Db2 in one transaction." />
      <ErrorNote error={error ?? ws.error} />

      <div className="grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="1 · Project" subtitle="Only folders inside the configured workspace roots can be scanned." icon={<FolderGit2 className="size-4" />} />
            <div className="grid gap-2 p-5 sm:grid-cols-2">
              {ws.loading && [0, 1].map((i) => <Skeleton key={i} className="h-16" />)}
              {ws.data?.items.map((w) => (
                <button key={w.path} onClick={() => setTarget(w.path)} disabled={!!running}
                  className={clsx('focus-ring flex items-center gap-3 rounded-xl p-3.5 text-left ring-1 transition',
                    target === w.path ? 'bg-brand-500/12 ring-brand-500/50' : 'bg-white/[0.02] ring-line hover:bg-white/[0.05]')}>
                  <div className={clsx('grid size-9 place-items-center rounded-lg', target === w.path ? 'bg-brand-500/20 text-brand-300' : 'bg-white/[0.05] text-muted')}>
                    <FolderGit2 className="size-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{w.name}</div>
                    <div className="mono truncate text-[11px] text-faint">{w.root.split(/[\\/]/).pop()}/{w.name}</div>
                  </div>
                </button>
              ))}
            </div>
            <div className="px-5 pb-5">
              <input value={target} onChange={(e) => setTarget(e.target.value)} disabled={!!running} spellCheck={false}
                placeholder="…or type a folder inside a workspace root"
                className="mono h-10 w-full rounded-xl bg-ink-950/60 px-3 text-sm outline-none ring-1 ring-line placeholder:text-faint focus:ring-brand-400/60" />
            </div>
          </Card>

          <Card>
            <CardHeader title="2 · Depth" icon={<Gauge className="size-4" />} />
            <div className="grid gap-2 p-5 sm:grid-cols-3">
              {PROFILES.map((p) => (
                <button key={p.id} onClick={() => setProfile(p.id)} disabled={!!running}
                  className={clsx('focus-ring rounded-xl p-4 text-left ring-1 transition',
                    profile === p.id ? 'bg-brand-500/12 ring-brand-500/50' : 'bg-white/[0.02] ring-line hover:bg-white/[0.05]')}>
                  <div className="flex items-center justify-between">
                    <p.icon className={clsx('size-4', profile === p.id ? 'text-brand-300' : 'text-muted')} />
                    <span className="mono text-[11px] text-faint">{p.time}</span>
                  </div>
                  <div className="mt-3 font-medium">{p.title}</div>
                  <div className="mt-1 text-xs leading-relaxed text-muted">{p.body}</div>
                </button>
              ))}
            </div>
          </Card>

          <ClickSpark sparkColor={['#78a9ff', '#be95ff', '#3ddbd9']} sparkCount={12} sparkRadius={34}>
            <Button variant="primary" size="lg" className="w-full" onClick={start} loading={starting || !!running}
              disabled={!target} icon={!running && <Radar className="size-4" />}>
              {running ? 'Scanning…' : '3 · Start scan'}
            </Button>
          </ClickSpark>
        </div>

        <Card className="relative overflow-hidden">
          <CardHeader title="Live progress" subtitle={job ? `${job.profile} · ${job.target.split(/[\\/]/).pop()}` : 'Waiting for a scan to start'} icon={<Radar className="size-4" />} />
          <div className="p-4">
            <AnimatePresence mode="wait">
              {!job && (
                <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="flex h-80 flex-col items-center justify-center text-center">
                  <div className="relative grid size-20 place-items-center">
                    <span className="absolute inset-0 animate-ping rounded-full bg-brand-500/10" />
                    <span className="absolute inset-3 rounded-full bg-brand-500/10 ring-1 ring-brand-500/30" />
                    <Radar className="relative size-7 text-brand-400" />
                  </div>
                  <DecryptedText text="Ready when you are" animateOn="view" speed={45} className="mt-6 text-sm text-muted" encryptedClassName="text-brand-500/60" />
                </motion.div>
              )}
              {job && (
                <motion.div key="job" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  {job.status === 'done' && s && job.gate && (
                    <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
                      className="mb-4 rounded-2xl p-5 ring-1"
                      style={{ background: `${GATE_META[job.gate].color}12`, boxShadow: `inset 0 0 0 1px ${GATE_META[job.gate].color}40` }}>
                      <GateBadge gate={job.gate} size="lg" />
                      <p className="mt-3 text-sm text-muted">{s.reason}</p>
                      <div className="mt-4 grid grid-cols-4 gap-2">
                        {(['critical', 'high', 'medium', 'low'] as const).map((k) => (
                          <div key={k} className="rounded-xl bg-ink-950/50 p-2.5 text-center ring-1 ring-line">
                            <div className="text-xl font-semibold" style={{ color: s[k] ? SEV_COLOR[k] : undefined }}>{s[k]}</div>
                            <div className="text-[11px] capitalize text-faint">{k}</div>
                          </div>
                        ))}
                      </div>
                      {job.warnings.map((w) => (
                        <div key={w} className="mt-3 flex gap-2 text-xs text-sev-medium"><AlertTriangle className="size-4 shrink-0" />{w}</div>
                      ))}
                      <div className="mt-4 flex gap-2">
                        {job.persisted && job.assessment_id && (
                          <Button variant="primary" onClick={() => navigate(`/assessments/${job.assessment_id}`)} icon={<ArrowRight className="size-4" />}>
                            Open full report
                          </Button>
                        )}
                        <Button variant="ghost" onClick={() => setJob(null)} icon={<RotateCcw className="size-4" />}>New scan</Button>
                      </div>
                    </motion.div>
                  )}
                  {job.status === 'failed' && (
                    <div className="mb-4 rounded-2xl bg-sev-critical/10 p-4 text-sm text-sev-critical ring-1 ring-sev-critical/30">{job.error}</div>
                  )}
                  <Stepper job={job} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </Card>
      </div>
      <p className="mt-6 text-center text-xs text-faint">
        Tip: press <span className="mono">N</span> anywhere to come back here. Past runs are in <Link to="/assessments" className="text-brand-400">Assessments</Link>.
      </p>
    </div>
  );
}
