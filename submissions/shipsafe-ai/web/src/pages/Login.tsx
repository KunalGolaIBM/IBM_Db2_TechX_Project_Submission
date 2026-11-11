import { motion } from 'motion/react';
import { ArrowRight, Database, KeyRound, Lock, ShieldCheck, Sparkles } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import Aurora from '@/components/reactbits/Aurora';
import BlurText from '@/components/reactbits/BlurText';
import ClickSpark from '@/components/reactbits/ClickSpark';
import GradientText from '@/components/reactbits/GradientText';
import { Logo } from '@/components/Shell';
import { Button, Kbd } from '@/components/ui';
import { useAuth } from '@/lib/auth';

const POINTS = [
  { icon: ShieldCheck, title: 'Deterministic release gate', body: 'Secrets, SQL injection, risky code, CVEs and tests, with one decision no model can override.' },
  { icon: Database, title: 'Every decision lives in IBM Db2', body: 'Assessments, findings, trends and an audit trail in relational tables you can query.' },
  { icon: Sparkles, title: 'Policies, cited by vector search', body: 'Each finding links to the exact team policy, ranked by VECTOR_DISTANCE inside Db2.' },
];

export default function Login() {
  const { signIn } = useAuth();
  const [token, setToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(token);
    } catch (err) {
      setError((err as Error).message === 'Invalid or revoked token' ? 'That token was not recognised or has been revoked.' : (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-full overflow-hidden bg-ink-950">
      <div className="absolute inset-x-0 top-0 h-[70vh]">
        <Aurora colorStops={['#0f62fe', '#a56eff', '#33b1ff']} amplitude={1.2} blend={0.6} speed={0.6} />
      </div>
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-ink-950/40 to-ink-950" />
      <div className="pointer-events-none absolute inset-0 grid-bg opacity-50" />

      <div className="relative mx-auto grid min-h-screen max-w-6xl items-center gap-14 px-6 py-12 lg:grid-cols-[1.15fr_1fr]">
        <div>
          <Logo />
          <div className="mt-14">
            <BlurText text="Know it's safe before you open the PR." animateBy="words" delay={90}
              className="text-4xl font-semibold leading-[1.08] tracking-tight text-fg sm:text-[56px]" />
            <div className="mt-5 text-lg text-muted">
              A production-readiness gate for every change, built on{' '}
              <GradientText colors={['#78a9ff', '#be95ff', '#3ddbd9', '#78a9ff']} animationSpeed={6} className="font-semibold">
                IBM Db2
              </GradientText>
              .
            </div>
          </div>
          <div className="mt-12 grid gap-5">
            {POINTS.map((p, i) => (
              <motion.div key={p.title} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 + i * 0.12 }}
                className="flex gap-4">
                <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/[0.06] text-brand-400 ring-1 ring-line">
                  <p.icon className="size-5" />
                </div>
                <div>
                  <div className="font-medium">{p.title}</div>
                  <div className="text-sm text-muted">{p.body}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        <motion.form onSubmit={submit} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, duration: 0.5 }}
          className="glass rounded-3xl bg-ink-900/60 p-8 shadow-glow">
          <div className="grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-violet-500">
            <Lock className="size-5 text-white" />
          </div>
          <h2 className="mt-6 text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1.5 text-sm text-muted">Paste your ShipSafe API token. It stays in this browser tab only.</p>
          <label className="mt-7 block text-xs font-medium uppercase tracking-wider text-faint" htmlFor="token">API token</label>
          <div className="mt-2 flex items-center gap-2 rounded-xl bg-ink-950/70 px-3 ring-1 ring-line focus-within:ring-brand-400/60">
            <KeyRound className="size-4 text-faint" />
            <input id="token" type="password" autoComplete="off" spellCheck={false} value={token} onChange={(e) => setToken(e.target.value)}
              placeholder="ss_…" className="mono h-12 w-full bg-transparent text-sm outline-none placeholder:text-faint" />
          </div>
          {error && <p className="mt-3 text-sm text-sev-critical">{error}</p>}
          <ClickSpark sparkColor={['#78a9ff', '#be95ff']} sparkCount={10} sparkRadius={26}>
            <Button type="submit" variant="primary" size="lg" loading={busy} disabled={token.trim().length < 10}
              className="mt-6 w-full" icon={!busy && <ArrowRight className="size-4" />}>
              Continue
            </Button>
          </ClickSpark>
          <div className="mt-7 rounded-xl bg-white/[0.03] p-4 text-[13px] leading-relaxed text-muted ring-1 ring-line">
            <div className="mb-1.5 font-medium text-fg">First time?</div>
            <p>
              <span className="mono text-brand-300">shipsafe serve</span> prints an admin token on its first start. Admins can issue
              more tokens from the Admin page or with <span className="mono text-brand-300">shipsafe token create</span>.
            </p>
            <div className="mt-3 flex items-center gap-2 text-faint">Tip: press <Kbd>Ctrl K</Kbd> anywhere once signed in.</div>
          </div>
        </motion.form>
      </div>
    </div>
  );
}
