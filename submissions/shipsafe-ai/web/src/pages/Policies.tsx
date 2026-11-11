import { AnimatePresence, motion } from 'motion/react';
import { BookOpenText, Database, Loader2, RefreshCw, Search, Sparkles } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import GradientText from '@/components/reactbits/GradientText';
import { Button, Card, CardHeader, ErrorNote, PageHeader, Skeleton } from '@/components/ui';
import { api, type PolicyHit } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { timeAgo } from '@/lib/format';
import { useApi } from '@/lib/hooks';

const EXAMPLES = [
  'How should I store the Db2 password?',
  'Is it OK to build a SQL query with an f-string?',
  'What do we do about a vulnerable PyYAML version?',
  'Can I call subprocess with shell=True?',
];

interface Doc { DOC_ID: string; TITLE: string; CATEGORY: string; VERSION: string; SOURCE: string; CHUNK_COUNT: number; INGESTED_AT: number }

function highlight(text: string, query: string) {
  // Render `inline code` from the policy Markdown, and mark words from the question.
  const words = query.toLowerCase().match(/[a-z0-9_]{4,}/g) ?? [];
  // Words are [a-z0-9_] only, so they are safe to join into a pattern without escaping.
  const re = words.length ? new RegExp(`(${words.join('|')})`, 'gi') : null;
  const mark = (t: string, k: string) =>
    re ? t.split(re).map((part, i) => (i % 2 === 1 ? <mark key={`${k}-${i}`} className="rounded bg-brand-500/25 px-0.5 text-fg">{part}</mark> : <span key={`${k}-${i}`}>{part}</span>)) : t;
  return text.split('`').map((chunk, i) =>
    i % 2 === 1 ? <code key={i} className="rounded-md bg-white/[0.07] px-1.5 py-0.5 text-[13px] text-brand-300">{mark(chunk, `c${i}`)}</code> : <span key={i}>{mark(chunk, `t${i}`)}</span>);
}

export default function Policies() {
  const { can } = useAuth();
  const docs = useApi<{ items: Doc[]; chunks: number }>('/api/policies');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<PolicyHit[] | null>(null);
  const [asked, setAsked] = useState('');
  const [latency, setLatency] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function ask(q: string, e?: FormEvent) {
    e?.preventDefault();
    if (q.trim().length < 2) return;
    setQuery(q);
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ results: PolicyHit[]; latency_ms: number }>('/api/policies/search', { method: 'POST', body: JSON.stringify({ query: q, top_k: 3 }) });
      setHits(res.results);
      setAsked(q);
      setLatency(res.latency_ms);
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  }

  async function reindex() {
    setReindexing(true);
    try {
      const res = await api<{ chunks: number }>('/api/policies/reindex', { method: 'POST' });
      toast.success(`Re-indexed ${res.chunks} policy chunks into Db2`);
      docs.reload();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setReindexing(false);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Knowledge base" title={<>Ask your <GradientText colors={['#78a9ff', '#be95ff', '#3ddbd9', '#78a9ff']} animationSpeed={6}>engineering policies</GradientText></>}
        description="Policies are split with LangChain and stored as VECTOR(384) embeddings in IBM Db2 through langchain-db2. Your question is ranked by VECTOR_DISTANCE inside the database, and the answer is the policy text itself, never generated."
        actions={can('admin') && <Button onClick={reindex} loading={reindexing} icon={<RefreshCw className="size-4" />}>Re-index</Button>} />

      <form onSubmit={(e) => ask(query, e)} className="glass flex items-center gap-3 rounded-2xl p-2 pl-5 shadow-glow">
        <Sparkles className="size-5 text-violet-400" />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask anything about how your team ships safely…"
          className="h-12 flex-1 bg-transparent text-[15px] outline-none placeholder:text-faint" />
        <Button type="submit" variant="primary" size="lg" loading={busy} disabled={query.trim().length < 2} icon={<Search className="size-4" />}>Ask</Button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button key={ex} onClick={() => ask(ex)} className="focus-ring rounded-full bg-white/[0.04] px-3 py-1.5 text-xs text-muted ring-1 ring-line transition hover:text-fg">{ex}</button>
        ))}
      </div>
      <div className="mt-4"><ErrorNote error={error} /></div>

      <AnimatePresence mode="wait">
        {busy && <motion.div key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-8 flex items-center gap-2 text-sm text-muted"><Loader2 className="size-4 animate-spin" /> Searching vectors in Db2…</motion.div>}
        {!busy && hits && (
          <motion.div key={asked} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-8 space-y-4">
            <div className="flex items-center gap-2 text-xs text-faint">
              <Database className="size-3.5" /> {hits.length} result{hits.length === 1 ? '' : 's'} for “{asked}”{latency !== null && ` · ${latency} ms in Db2`}
            </div>
            {hits.map((h, i) => (
              <motion.div key={h.doc_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
                <Card className={i === 0 ? 'ring-1 ring-violet-500/30' : ''}>
                  <div className="p-6">
                    <div className="flex flex-wrap items-center gap-3">
                      {i === 0 && <span className="rounded-full bg-violet-500/15 px-2.5 py-0.5 text-[11px] font-medium text-violet-400">Best match</span>}
                      <span className="mono text-xs text-faint">{h.doc_id} v{h.version}</span>
                      <span className="text-xs text-faint">section “{h.section}”</span>
                      <div className="ml-auto flex items-center gap-2">
                        <div className="h-1.5 w-28 overflow-hidden rounded-full bg-white/[0.06]">
                          <motion.div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-brand-400" initial={{ width: 0 }}
                            animate={{ width: `${Math.min(100, Math.max(6, h.similarity * 300))}%` }} />
                        </div>
                        <span className="mono text-[11px] text-faint">{h.similarity.toFixed(3)}</span>
                      </div>
                    </div>
                    <h3 className="mt-3 text-lg font-semibold">{h.title}</h3>
                    <p className="mt-2 whitespace-pre-line text-[14.5px] leading-relaxed text-muted">{highlight(h.content.replace(/^#+ .*\n/gm, ''), asked)}</p>
                    <div className="mono mt-4 text-[11px] text-faint">source: {h.source}</div>
                  </div>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <Card className="mt-10">
        <CardHeader title="Indexed policies" subtitle={docs.data ? `${docs.data.items.length} documents · ${docs.data.chunks} vector chunks in POLICY_VECTORS` : 'Loading…'} icon={<BookOpenText className="size-4" />} />
        <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">
          {docs.loading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}
          {docs.data?.items.map((d) => (
            <button key={d.DOC_ID} onClick={() => ask(d.TITLE)} className="focus-ring rounded-xl bg-white/[0.02] p-4 text-left ring-1 ring-line transition hover:bg-white/[0.05]">
              <div className="mono text-[11px] text-brand-400">{d.DOC_ID} · v{d.VERSION}</div>
              <div className="mt-1.5 font-medium leading-snug">{d.TITLE}</div>
              <div className="mt-2 text-xs text-faint">{d.CATEGORY} · {d.CHUNK_COUNT} chunks · indexed {timeAgo(Number(d.INGESTED_AT))}</div>
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}
