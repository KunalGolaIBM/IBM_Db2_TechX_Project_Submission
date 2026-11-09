import { ChevronLeft, ChevronRight, Plus, Search } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useComplaints, useCreateComplaint } from '../api/queries'
import type { Complaint } from '../api/schemas'
import { useAuth } from '../auth/AuthContext'
import { ComplaintStatusBadge, SeverityDots, SyntheticBadge } from '../components/Badges'
import { ComplaintDetail } from '../components/ComplaintDetail'
import { Modal } from '../components/Modal'
import { ErrorNotice, SuccessNotice, SyntheticBanner } from '../components/Notices'
import {
  Button,
  Card,
  Checkbox,
  Chip,
  EmptyState,
  LoadingBlock,
  PageHeader,
  SelectInput,
  TextArea,
  TextInput,
} from '../components/ui'
import {
  CATEGORIES,
  CATEGORY_LABEL,
  COMPLAINT_STATUSES,
  COMPLAINT_STATUS_LABEL,
  SEVERITY_LABEL,
  type Category,
  type ComplaintStatus,
} from '../lib/domain'
import { formatDateTime, formatInt } from '../lib/format'
import { isValid, validateComplaint } from '../lib/validation'

const PAGE_SIZE = 20
type Sort = 'newest' | 'severity' | 'id'

function matches(c: Complaint, term: string): boolean {
  const t = term.trim().toLowerCase()
  if (!t) return true
  // a purely numeric query (optionally "#12") means "this complaint ID", so deep links land on exactly one record
  const asId = /^#?(\d+)$/.exec(t)
  if (asId) return String(c.complaint_id) === asId[1]
  return (
    c.title.toLowerCase().includes(t) ||
    c.description.toLowerCase().includes(t) ||
    (c.ward ?? '').toLowerCase().includes(t) ||
    (c.external_ref ?? '').toLowerCase().includes(t)
  )
}

export function ComplaintsView() {
  const { can } = useAuth()
  const [params] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') ?? '')
  const [category, setCategory] = useState<'all' | Category>('all')
  const [status, setStatus] = useState<'all' | ComplaintStatus>('all')
  const [provenance, setProvenance] = useState<'all' | 'synthetic' | 'real'>('all')
  const [sort, setSort] = useState<Sort>('newest')
  const [page, setPage] = useState(1)
  const [openId, setOpenId] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const q = useComplaints({ limit: 200 })

  const rows = useMemo(() => {
    const filtered = (q.data ?? []).filter(
      (c) =>
        matches(c, search) &&
        (category === 'all' || c.category === category) &&
        (status === 'all' || c.status === status) &&
        (provenance === 'all' || (provenance === 'synthetic') === c.is_synthetic),
    )
    return [...filtered].sort((a, b) =>
      sort === 'severity'
        ? b.severity - a.severity || b.complaint_id - a.complaint_id
        : sort === 'id'
          ? a.complaint_id - b.complaint_id
          : b.reported_at.localeCompare(a.reported_at) || b.complaint_id - a.complaint_id,
    )
  }, [q.data, search, category, status, provenance, sort])

  if (q.isPending) return <LoadingBlock label="Loading complaints" className="min-h-96" />
  if (!q.data) return <ErrorNotice error={q.error} onRetry={() => void q.refetch()} />

  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const current = Math.min(page, pages)
  const pageRows = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)
  const open = q.data.find((c) => c.complaint_id === openId)
  const onFilter = <T,>(set: (v: T) => void) => (v: T) => {
    set(v)
    setPage(1)
  }

  return (
    <div className="flex flex-col gap-5" data-testid="complaints-view">
      <PageHeader
        title="Complaints"
        description="Browse the complaint records stored in IBM Db2. Search, filter and open any record."
        actions={
          can('complaint:create') ? (
            <Button variant="primary" onClick={() => setCreating(true)} icon={<Plus className="size-4" aria-hidden />}>
              Report a complaint
            </Button>
          ) : (
            <Chip title="Only analysts can add complaints">Read-only for your role</Chip>
          )
        }
      />
      <SyntheticBanner synthetic={q.data.filter((c) => c.is_synthetic).length} total={q.data.length} />

      <Card>
        <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_1fr_1fr_1fr_1fr]">
          <TextInput
            label="Search"
            type="search"
            value={search}
            onChange={(e) => onFilter(setSearch)(e.target.value)}
            placeholder="Title, description, ward, or an ID such as #12"
            data-testid="complaint-search"
          />
          <SelectInput label="Category" value={category} onChange={(e) => onFilter(setCategory)(e.target.value as 'all' | Category)}>
            <option value="all">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>
            ))}
          </SelectInput>
          <SelectInput label="Status" value={status} onChange={(e) => onFilter(setStatus)(e.target.value as 'all' | ComplaintStatus)}>
            <option value="all">All statuses</option>
            {COMPLAINT_STATUSES.map((s) => (
              <option key={s} value={s}>{COMPLAINT_STATUS_LABEL[s]}</option>
            ))}
          </SelectInput>
          <SelectInput
            label="Record type"
            value={provenance}
            onChange={(e) => onFilter(setProvenance)(e.target.value as 'all' | 'synthetic' | 'real')}
          >
            <option value="all">All records</option>
            <option value="synthetic">Synthetic only</option>
            <option value="real">Real reports only</option>
          </SelectInput>
          <SelectInput label="Sort by" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="newest">Newest first</option>
            <option value="severity">Most severe first</option>
            <option value="id">ID</option>
          </SelectInput>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-3 border-b border-ink-700 px-5 py-3">
          <p className="text-[13px] text-fg-2" aria-live="polite" data-testid="complaint-count">
            <strong className="font-semibold text-fg">{formatInt(rows.length)}</strong> of {formatInt(q.data.length)} loaded complaints
          </p>
        </div>
        {rows.length === 0 ? (
          <EmptyState icon={<Search />} title="No complaints match your filters">
            Try a different search term or clear a filter.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="complaint-table">
              <caption className="sr-only">Complaints</caption>
              <thead>
                <tr className="border-b border-ink-700 text-left text-xs text-fg-2">
                  <th scope="col" className="px-2 py-2.5 font-medium sm:px-4">ID</th>
                  <th scope="col" className="px-2 py-2.5 font-medium sm:px-4">Complaint</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">Category</th>
                  <th scope="col" className="px-2 py-2.5 font-medium sm:px-4">Severity</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium xl:table-cell">Status</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">Reported</th>
                  <th scope="col" className="px-2 py-2.5 font-medium sm:px-4">Record</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((c) => (
                  <tr
                    key={c.complaint_id}
                    data-testid="complaint-row"
                    data-complaint-id={c.complaint_id}
                    className="border-b border-ink-700/60 last:border-0 hover:bg-ink-750/50"
                  >
                    <td className="px-2 py-2.5 font-mono text-xs text-fg-2 sm:px-4">#{c.complaint_id}</td>
                    <td className="max-w-sm px-2 py-2.5 sm:px-4">
                      <button
                        type="button"
                        onClick={() => setOpenId(c.complaint_id)}
                        className="line-clamp-1 text-left font-medium text-fg hover:text-copper-300"
                      >
                        {c.title}
                      </button>
                      <span className="block text-xs text-fg-3">{c.ward ?? 'No ward'}</span>
                    </td>
                    <td className="hidden px-4 py-2.5 text-fg-2 md:table-cell">{CATEGORY_LABEL[c.category]}</td>
                    <td className="px-2 py-2.5 sm:px-4"><SeverityDots severity={c.severity} /></td>
                    <td className="hidden px-4 py-2.5 xl:table-cell"><ComplaintStatusBadge status={c.status} /></td>
                    <td className="hidden px-4 py-2.5 whitespace-nowrap text-fg-2 md:table-cell">{formatDateTime(c.reported_at)}</td>
                    <td className="px-2 py-2.5 sm:px-4">{c.is_synthetic ? <SyntheticBadge /> : <Chip tone="good">Real report</Chip>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {pages > 1 && (
          <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-ink-700 px-5 py-3">
            <Button size="sm" disabled={current <= 1} onClick={() => setPage(current - 1)} icon={<ChevronLeft className="size-4" aria-hidden />}>
              Previous
            </Button>
            <span className="text-[13px] text-fg-2" data-testid="page-indicator">
              Page {current} of {pages}
            </span>
            <Button size="sm" disabled={current >= pages} onClick={() => setPage(current + 1)} icon={<ChevronRight className="size-4" aria-hidden />}>
              Next
            </Button>
          </nav>
        )}
      </Card>

      <Modal open={open !== undefined} onClose={() => setOpenId(null)} title={open ? `Complaint #${open.complaint_id}` : 'Complaint'} size="lg">
        {open && (
          <ComplaintDetail
            complaint={open}
            actions={
              <Link to={`/map?complaint=${open.complaint_id}`} className="inline-flex h-9 items-center rounded-lg border border-ink-600 bg-ink-750 px-4 text-sm text-fg hover:bg-ink-700">
                Show on map
              </Link>
            }
          />
        )}
      </Modal>
      {creating && <NewComplaintModal onClose={() => setCreating(false)} />}
    </div>
  )
}

function NewComplaintModal({ onClose }: { onClose: () => void }) {
  const create = useCreateComplaint()
  const [form, setForm] = useState({
    category: 'POTHOLE' as Category,
    title: '',
    description: '',
    latitude: '',
    longitude: '',
    ward: '',
    severity: '3',
    synthetic: true,
  })
  const [submitted, setSubmitted] = useState(false)
  const errors = validateComplaint(form)
  const show = (k: keyof typeof errors) => (submitted ? (errors[k] ?? null) : null)
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))
  const result = create.data

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (!isValid(errors)) return
    create.mutate({
      category: form.category,
      title: form.title.trim(),
      description: form.description.trim(),
      latitude: Number(form.latitude),
      longitude: Number(form.longitude),
      ward: form.ward.trim() || null,
      severity: Number(form.severity),
      source: 'DASHBOARD',
      is_synthetic: form.synthetic,
    })
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Report a complaint"
      size="lg"
      footer={
        result ? (
          <Button variant="primary" onClick={onClose}>Done</Button>
        ) : (
          <>
            <Button onClick={onClose}>Cancel</Button>
            <Button variant="primary" type="submit" form="new-complaint-form" loading={create.isPending}>
              Create complaint
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="flex flex-col gap-4" data-testid="complaint-created">
          <SuccessNotice title={`Complaint #${result.complaint.complaint_id} created`}>
            Stored in IBM Db2 in geo-cell <code className="font-mono text-fg">{result.complaint.geo_cell}</code>
            {result.complaint.is_synthetic ? ' and marked SYNTHETIC.' : '.'}
          </SuccessNotice>
          <div>
            <h3 className="text-sm font-semibold text-fg">Possible duplicates found by Db2</h3>
            <p className="text-[13px] text-fg-2">Same category within 250 m and 14 days, ranked by distance and text similarity.</p>
            {result.duplicate_candidates.length === 0 ? (
              <p className="mt-2 text-sm text-fg-2">No likely duplicates were found.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-1.5" data-testid="duplicate-candidates">
                {result.duplicate_candidates.map((d) => (
                  <li key={d.complaint_id} className="rounded-lg border border-ink-700 bg-ink-850 px-3 py-2 text-sm">
                    <span className="font-mono text-xs text-fg-3">#{d.complaint_id}</span> <span className="text-fg">{d.title}</span>
                    <span className="block text-xs text-fg-2">
                      {d.distance_m.toFixed(0)} m away · text similarity {(d.text_similarity * 100).toFixed(0)}% · score {d.score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : (
        <form id="new-complaint-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          {create.isError && <ErrorNotice error={create.error} />}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <SelectInput label="Category" value={form.category} onChange={(e) => set('category', e.target.value as Category)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>
              ))}
            </SelectInput>
            <SelectInput label="Severity" value={form.severity} onChange={(e) => set('severity', e.target.value)}>
              {[1, 2, 3, 4, 5].map((s) => (
                <option key={s} value={s}>{s} · {SEVERITY_LABEL[s]}</option>
              ))}
            </SelectInput>
          </div>
          <TextInput label="Title" value={form.title} onChange={(e) => set('title', e.target.value)} error={show('title')} data-autofocus />
          <TextArea label="Description" value={form.description} onChange={(e) => set('description', e.target.value)} error={show('description')} />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <TextInput label="Latitude" inputMode="decimal" value={form.latitude} onChange={(e) => set('latitude', e.target.value)} error={show('latitude')} hint="Decimal degrees" />
            <TextInput label="Longitude" inputMode="decimal" value={form.longitude} onChange={(e) => set('longitude', e.target.value)} error={show('longitude')} hint="Decimal degrees" />
            <TextInput label="Ward (optional)" value={form.ward} onChange={(e) => set('ward', e.target.value)} error={show('ward')} />
          </div>
          <Checkbox
            label="Mark as a synthetic demonstration record"
            checked={form.synthetic}
            onChange={(e) => set('synthetic', e.target.checked)}
          />
        </form>
      )}
    </Modal>
  )
}

