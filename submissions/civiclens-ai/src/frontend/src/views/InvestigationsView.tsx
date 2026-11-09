import { FolderSearch, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useCreateInvestigation, useInvestigations } from '../api/queries'
import { useAuth } from '../auth/AuthContext'
import { InvestigationStatusBadge } from '../components/Badges'
import { Modal } from '../components/Modal'
import { ErrorNotice } from '../components/Notices'
import { Button, Card, Chip, EmptyState, LoadingBlock, PageHeader, TextArea, TextInput, ToggleChip } from '../components/ui'
import { INVESTIGATION_STATUSES, INVESTIGATION_STATUS_LABEL, type InvestigationStatus } from '../lib/domain'
import { formatDateTime } from '../lib/format'
import { isValid, validateInvestigation } from '../lib/validation'

export function InvestigationsView() {
  const { can } = useAuth()
  const [status, setStatus] = useState<InvestigationStatus | undefined>(undefined)
  const [creating, setCreating] = useState(false)
  const q = useInvestigations(status)

  return (
    <div className="flex flex-col gap-5" data-testid="investigations-view">
      <PageHeader
        title="Investigation workspace"
        description="An investigation poses a question, gathers evidence from the complaint database, and ends in recommendations that people review."
        actions={
          can('investigation:create') ? (
            <Button variant="primary" onClick={() => setCreating(true)} icon={<Plus className="size-4" aria-hidden />}>
              New investigation
            </Button>
          ) : (
            <Chip title="Only analysts create investigations">Read-only for your role</Chip>
          )
        }
      />

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by status">
        <ToggleChip pressed={status === undefined} onToggle={() => setStatus(undefined)}>
          All
        </ToggleChip>
        {INVESTIGATION_STATUSES.map((s) => (
          <ToggleChip key={s} pressed={status === s} onToggle={() => setStatus(status === s ? undefined : s)}>
            {INVESTIGATION_STATUS_LABEL[s]}
          </ToggleChip>
        ))}
      </div>

      <Card>
        {q.isPending ? (
          <LoadingBlock label="Loading investigations" />
        ) : !q.data ? (
          <div className="p-5">
            <ErrorNotice error={q.error} onRetry={() => void q.refetch()} />
          </div>
        ) : q.data.length === 0 ? (
          <EmptyState icon={<FolderSearch />} title="No investigations yet">
            {can('investigation:create')
              ? 'Create one to start gathering evidence and generating recommendations.'
              : 'Analysts create investigations; they will appear here.'}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="investigation-table">
              <caption className="sr-only">Investigations</caption>
              <thead>
                <tr className="border-b border-ink-700 text-left text-xs text-fg-2">
                  <th scope="col" className="px-2 py-2.5 font-medium sm:px-4">ID</th>
                  <th scope="col" className="px-2 py-2.5 font-medium sm:px-4">Investigation</th>
                  <th scope="col" className="px-2 py-2.5 font-medium sm:px-4">Status</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">Created by</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">Created</th>
                  <th scope="col" className="hidden px-4 py-2.5 font-medium xl:table-cell">Closed</th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((inv) => (
                  <tr
                    key={inv.investigation_id}
                    data-testid="investigation-row"
                    data-investigation-id={inv.investigation_id}
                    className="border-b border-ink-700/60 last:border-0 hover:bg-ink-750/50"
                  >
                    <td className="px-2 py-2.5 font-mono text-xs text-fg-2 sm:px-4">#{inv.investigation_id}</td>
                    <td className="max-w-md px-2 py-2.5 sm:px-4">
                      <Link to={`/investigations/${inv.investigation_id}`} className="line-clamp-1 font-medium text-fg hover:text-copper-300">
                        {inv.title}
                      </Link>
                    </td>
                    <td className="px-2 py-2.5 sm:px-4"><InvestigationStatusBadge status={inv.status} /></td>
                    <td className="hidden px-4 py-2.5 text-fg-2 md:table-cell">{inv.created_by}</td>
                    <td className="hidden px-4 py-2.5 whitespace-nowrap text-fg-2 md:table-cell">{formatDateTime(inv.created_at)}</td>
                    <td className="hidden px-4 py-2.5 whitespace-nowrap text-fg-2 xl:table-cell">{inv.closed_at ? formatDateTime(inv.closed_at) : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {creating && <NewInvestigationModal onClose={() => setCreating(false)} />}
    </div>
  )
}

function NewInvestigationModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const create = useCreateInvestigation()
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const errors = validateInvestigation({ title, question })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (!isValid(errors)) return
    create.mutate(
      { title: title.trim(), question: question.trim() },
      { onSuccess: (inv) => navigate(`/investigations/${inv.investigation_id}`) },
    )
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="New investigation"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="new-investigation-form" loading={create.isPending}>
            Create investigation
          </Button>
        </>
      }
    >
      <form id="new-investigation-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {create.isError && <ErrorNotice error={create.error} />}
        <TextInput
          label="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={submitted ? (errors.title ?? null) : null}
          placeholder="e.g. Pothole cluster triage"
          data-autofocus
        />
        <TextArea
          label="Question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          error={submitted ? (errors.question ?? null) : null}
          hint="What do you want to find out? The question is recorded with the investigation."
          placeholder="e.g. Which neighbourhoods should repair crews visit first?"
        />
        <p className="text-[13px] leading-5 text-fg-2">
          You will be recorded as the investigation’s creator. Because of the four-eyes rule, you cannot review its
          recommendations yourself.
        </p>
      </form>
    </Modal>
  )
}
