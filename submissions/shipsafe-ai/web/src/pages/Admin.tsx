import clsx from 'clsx';
import { motion } from 'motion/react';
import { Copy, KeyRound, Plus, ScrollText, ShieldOff } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { Button, Card, CardHeader, ErrorNote, PageHeader, Skeleton } from '@/components/ui';
import { api, type Role } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { dateTime, timeAgo } from '@/lib/format';
import { useApi } from '@/lib/hooks';

interface TokenRow { TOKEN_ID: string; NAME: string; ROLE: Role; CREATED_AT: number; LAST_USED_AT: number | null; REVOKED: number }
interface AuditRow { EVENT_ID: string; TS: number; ACTOR: string; ROLE: string | null; ACTION: string; TARGET: string | null; OUTCOME: string; DETAIL: string | null; CLIENT_IP: string | null }

/** Show only the tail of filesystem paths; the full path stays in Db2 (hover shows it). */
function shortTarget(target: string | null): string | null {
  if (!target || !/[\\/]/.test(target)) return target;
  const parts = target.split(/[\\/]/).filter(Boolean);
  return parts.length > 2 ? `…/${parts.slice(-2).join('/')}` : target;
}

const ROLE_HELP: Record<Role, string> = {
  viewer: 'Read dashboards, reports and policies',
  operator: 'Viewer + run scans and compare runs',
  admin: 'Operator + tokens, audit log, re-index',
};

export default function Admin() {
  const { me } = useAuth();
  const tokens = useApi<{ items: TokenRow[] }>('/api/tokens');
  const audit = useApi<{ items: AuditRow[] }>('/api/audit?limit=150', 15000);
  const [name, setName] = useState('');
  const [role, setRole] = useState<Role>('viewer');
  const [created, setCreated] = useState<{ token: string; name: string } | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ token: string; name: string }>('/api/tokens', { method: 'POST', body: JSON.stringify({ name, role }) });
      setCreated(res);
      setName('');
      tokens.reload();
      audit.reload();
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    if (!window.confirm('Revoke this token? Anything using it will lose access immediately.')) return;
    try {
      await api(`/api/tokens/${id}`, { method: 'DELETE' });
      toast.success('Token revoked');
      tokens.reload();
      audit.reload();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Administration" title="Access & audit"
        description="API tokens are stored only as SHA-256 hashes in Db2 API_TOKENS. Every scan, token change and denied request is written to the Db2 AUDIT_LOG." />
      <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader title="Issue a token" subtitle="Give each person or CI job its own token with the least role it needs." icon={<KeyRound className="size-4" />} />
            <form onSubmit={create} className="space-y-4 p-5">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. ci-pipeline or priya"
                className="h-11 w-full rounded-xl bg-ink-950/60 px-3 text-sm outline-none ring-1 ring-line placeholder:text-faint focus:ring-brand-400/60" />
              <div className="grid gap-2 sm:grid-cols-3">
                {(['viewer', 'operator', 'admin'] as Role[]).map((r) => (
                  <button type="button" key={r} onClick={() => setRole(r)}
                    className={clsx('focus-ring rounded-xl p-3 text-left ring-1 transition', role === r ? 'bg-brand-500/12 ring-brand-500/50' : 'ring-line hover:bg-white/[0.04]')}>
                    <div className="text-sm font-medium capitalize">{r}</div>
                    <div className="mt-0.5 text-[11px] leading-snug text-muted">{ROLE_HELP[r]}</div>
                  </button>
                ))}
              </div>
              <ErrorNote error={error} />
              <Button type="submit" variant="primary" loading={busy} disabled={name.trim().length < 2} icon={<Plus className="size-4" />}>Create token</Button>
            </form>
            {created && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mx-5 mb-5 rounded-xl bg-ok/[0.07] p-4 ring-1 ring-ok/25">
                <div className="text-sm font-medium text-ok">Token for “{created.name}”. Copy it now: it won't be shown again.</div>
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-ink-950/70 p-2 pl-3 ring-1 ring-line">
                  <code className="flex-1 truncate text-xs">{created.token}</code>
                  <Button size="sm" onClick={() => { navigator.clipboard.writeText(created.token); toast.success('Copied'); }} icon={<Copy className="size-3.5" />}>Copy</Button>
                </div>
              </motion.div>
            )}
          </Card>

          <Card>
            <CardHeader title="Tokens" icon={<KeyRound className="size-4" />} />
            <div className="space-y-1 p-3">
              {tokens.loading && <Skeleton className="h-24" />}
              {tokens.data?.items.map((t) => (
                <div key={t.TOKEN_ID} className={clsx('flex items-center gap-3 rounded-xl px-3 py-2.5', t.REVOKED ? 'opacity-45' : 'hover:bg-white/[0.03]')}>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      {t.NAME}
                      {t.TOKEN_ID === me?.token_id && <span className="rounded bg-brand-500/15 px-1.5 text-[10px] text-brand-300">you</span>}
                    </div>
                    <div className="mono text-[11px] text-faint">{t.TOKEN_ID} · {t.REVOKED ? 'revoked' : t.LAST_USED_AT ? `used ${timeAgo(t.LAST_USED_AT)}` : 'never used'}</div>
                  </div>
                  <span className="mono rounded-md bg-white/[0.05] px-2 py-0.5 text-[11px] capitalize text-muted">{t.ROLE}</span>
                  {!t.REVOKED && t.TOKEN_ID !== me?.token_id && (
                    <button onClick={() => revoke(t.TOKEN_ID)} title="Revoke" className="focus-ring rounded-lg p-1.5 text-muted hover:bg-sev-critical/10 hover:text-sev-critical">
                      <ShieldOff className="size-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader title="Audit trail" subtitle="Append-only events from Db2 AUDIT_LOG (refreshes every 15 s)" icon={<ScrollText className="size-4" />} />
          <div className="scroll-thin max-h-[720px] overflow-y-auto p-3">
            {audit.loading && <Skeleton className="h-64" />}
            {audit.data?.items.map((e) => (
              <div key={e.EVENT_ID} className="grid grid-cols-[auto_1fr] gap-x-3 rounded-xl px-3 py-2.5 hover:bg-white/[0.025]">
                <span className={clsx('mt-1.5 size-2 rounded-full', e.OUTCOME === 'success' ? 'bg-ok' : e.OUTCOME === 'denied' ? 'bg-sev-high' : 'bg-sev-critical')} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2 text-sm">
                    <span className="mono font-medium">{e.ACTION}</span>
                    <span className="text-muted">by {e.ACTOR}</span>
                    <span className="ml-auto text-[11px] text-faint">{dateTime(e.TS)}</span>
                  </div>
                  {(e.TARGET || e.DETAIL) && (
                    <div className="mono truncate text-[11px] text-faint" title={e.TARGET ?? undefined}>
                      {[shortTarget(e.TARGET), e.DETAIL].filter(Boolean).join(' · ')}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
