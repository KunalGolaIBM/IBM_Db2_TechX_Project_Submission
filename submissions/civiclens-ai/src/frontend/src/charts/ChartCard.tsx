import { ChartColumn, Table2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Button, Card, CardBody, CardHeader } from '../components/ui'
import { cn } from '../lib/cn'

/** A card that owns a chart's title and its table-view twin (the accessible equivalent of the plot). */
export function ChartCard({
  title,
  subtitle,
  children,
  table,
  footer,
  dimmed = false,
  testId,
  className,
}: {
  title: string
  subtitle?: ReactNode
  children: ReactNode
  table: ReactNode
  footer?: ReactNode
  dimmed?: boolean
  testId?: string
  className?: string
}) {
  const [asTable, setAsTable] = useState(false)
  return (
    <Card data-testid={testId} className={className}>
      <CardHeader
        title={title}
        subtitle={subtitle}
        actions={
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={asTable}
            onClick={() => setAsTable((v) => !v)}
            icon={asTable ? <ChartColumn className="size-3.5" aria-hidden /> : <Table2 className="size-3.5" aria-hidden />}
          >
            {asTable ? 'View chart' : 'View as table'}
          </Button>
        }
      />
      {/* previous data stays on screen (dimmed) while refetching: no skeleton flash, no layout jump */}
      <CardBody className={cn('transition-opacity', dimmed && 'opacity-60')}>
        {asTable ? table : children}
        {footer}
      </CardBody>
    </Card>
  )
}

export interface TableColumn {
  key: string
  label: string
  numeric?: boolean
}

export function DataTable({
  caption,
  columns,
  rows,
}: {
  caption: string
  columns: TableColumn[]
  rows: Array<Record<string, ReactNode>>
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="data-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-ink-700 text-left text-xs text-fg-2">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={cn('px-2 py-2 font-medium', c.numeric && 'text-right')}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-ink-700/60 last:border-0">
              {columns.map((c) => (
                <td key={c.key} className={cn('px-2 py-1.5 text-fg', c.numeric && 'text-right tabular-nums')}>
                  {row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
