import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ChartCard, DataTable } from '../src/charts/ChartCard'
import { ColumnChart } from '../src/charts/ColumnChart'
import { RankedBars } from '../src/charts/RankedBars'
import { SegmentedBar } from '../src/charts/SegmentedBar'
import { TrendChart } from '../src/charts/TrendChart'

const bars = [
  { key: 'POTHOLE', label: 'Pothole', value: 13, note: 'avg severity 3.4' },
  { key: 'WATER_LEAK', label: 'Water leak', value: 11 },
  { key: 'TRAFFIC_SIGNAL', label: 'Traffic signal', value: 1 },
]

describe('RankedBars', () => {
  it('prints each value at the bar tip and names every bar', () => {
    render(<RankedBars data={bars} ariaLabel="Complaints by category" />)
    const rows = screen.getAllByTestId('bar-row')
    expect(rows.map((r) => r.getAttribute('data-value'))).toEqual(['13', '11', '1'])
    expect(within(rows[0]).getByText('Pothole')).toBeInTheDocument()
    expect(within(rows[0]).getByText('13')).toBeInTheDocument()
    expect(rows[0]).toHaveAccessibleName('Pothole: 13 complaints')
  })

  it('scales bar length to the maximum and keeps even a tiny value visible', () => {
    render(<RankedBars data={bars} ariaLabel="x" />)
    const fills = screen.getAllByTestId('bar-row').map((r) => r.querySelector<HTMLElement>('span[style*="width"]')!)
    expect(fills[0].style.width).toBe('calc(100% - 3rem)') // the largest value fills the track (minus room for its label)
    expect(fills[1].style.width).toMatch(/84\.61/) // 11/13 of it (jsdom expands the calc)
    expect(fills[2].style.minWidth).toBe('3px')
  })

  it('shows a tooltip on hover with the value first, then label and share', () => {
    render(<RankedBars data={bars} ariaLabel="x" />)
    const row = screen.getAllByTestId('bar-row')[0]
    fireEvent.pointerMove(row, { clientX: 20, clientY: 20 })
    const tip = screen.getByRole('tooltip')
    expect(tip).toHaveTextContent('13 complaints')
    expect(tip).toHaveTextContent('52% of total')
    expect(tip).toHaveTextContent('avg severity 3.4')
    fireEvent.pointerLeave(row)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('shows the same tooltip on keyboard focus (tooltips never gate information)', async () => {
    const user = userEvent.setup()
    render(<RankedBars data={bars} ariaLabel="x" />)
    await user.tab()
    expect(screen.getByRole('tooltip')).toHaveTextContent('13 complaints')
  })

  it('renders an empty state instead of an empty plot', () => {
    render(<RankedBars data={[]} ariaLabel="x" />)
    expect(screen.getByText('No data yet')).toBeInTheDocument()
  })
})

describe('ColumnChart', () => {
  const columns = [1, 2, 3, 4, 5].map((n) => ({ key: String(n), label: String(n), sublabel: ['Minor', 'Low', 'Moderate', 'High', 'Critical'][n - 1], value: n * 2, color: '#d67f46' }))

  it('labels every column with its value and names the scale', () => {
    render(<ColumnChart data={columns} ariaLabel="Complaints by severity" />)
    expect(screen.getAllByTestId('column').map((c) => c.getAttribute('data-value'))).toEqual(['2', '4', '6', '8', '10'])
    expect(screen.getByRole('img', { name: 'Severity 5 (Critical): 10 complaints' })).toBeInTheDocument()
    expect(screen.getByText('Critical')).toBeInTheDocument()
  })

  it('never draws a column wider than 24px', () => {
    const { container } = render(<ColumnChart data={columns} ariaLabel="x" />)
    for (const path of container.querySelectorAll('path')) {
      const xs = [...(path.getAttribute('d') ?? '').matchAll(/[ML]([\d.]+),/g)].map((m) => Number(m[1]))
      expect(Math.max(...xs) - Math.min(...xs)).toBeLessThanOrEqual(24.01)
    }
  })

  it('shows a tooltip on keyboard focus', async () => {
    const user = userEvent.setup()
    render(<ColumnChart data={columns} ariaLabel="x" />)
    await user.tab()
    expect(screen.getByRole('tooltip')).toHaveTextContent('2 complaints')
  })
})

describe('SegmentedBar', () => {
  const parts = [
    { key: 'a', label: 'Rule-based · no LLM', value: 99, color: '#3987e5' },
    { key: 'b', label: 'AI model (LLM)', value: 1, color: '#cc7233' },
    { key: 'c', label: 'Manual · analyst', value: 0, color: '#199e70' },
  ]

  it('draws no block for a zero part and lists only the parts that exist in the legend', () => {
    render(<SegmentedBar data={parts} ariaLabel="By generator" />)
    expect(screen.getAllByTestId('segment')).toHaveLength(2)
    const legend = screen.getByRole('list', { name: 'Legend' })
    expect(within(legend).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Rule-based · no LLM', 'AI model (LLM)'])
    expect(legend.textContent).not.toMatch(/\d/) // the legend names parts; it does not repeat numbers
  })

  it('prints a share only where the block is wide enough to hold it', () => {
    render(<SegmentedBar data={parts} ariaLabel="By generator" />)
    const [wide, narrow] = screen.getAllByTestId('segment')
    expect(wide).toHaveTextContent('99%')
    expect(narrow.textContent).toBe('') // 1% of the bar: no label rather than a clipped one
    expect(narrow).toHaveAccessibleName('AI model (LLM): 1 recommendations, 1%') // ...but the value is still reachable
  })

  it('exposes every part, count and share in the group name', () => {
    render(<SegmentedBar data={parts} ariaLabel="By generator" />)
    expect(screen.getByRole('group', { name: /Rule-based · no LLM 99 \(99%\), AI model \(LLM\) 1 \(1%\)/ })).toBeInTheDocument()
  })

  it('shows an empty state when there is nothing to split', () => {
    render(<SegmentedBar data={parts.map((p) => ({ ...p, value: 0 }))} ariaLabel="x" />)
    expect(screen.getByText('Nothing to show yet')).toBeInTheDocument()
  })
})

describe('TrendChart', () => {
  const points = Array.from({ length: 10 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, count: i === 6 ? 9 : i % 3 }))

  it('describes itself, including the peak, for screen readers', () => {
    render(<TrendChart points={points} ariaLabel="New complaints per day." />)
    expect(screen.getByRole('img', { name: /Peak: 9 on 07 Oct/ })).toBeInTheDocument()
  })

  it('steps through days with the arrow keys and reads each one out', async () => {
    const user = userEvent.setup()
    render(<TrendChart points={points} ariaLabel="x" />)
    await user.tab()
    await user.keyboard('{End}')
    expect(screen.getByRole('tooltip')).toHaveTextContent('10 Oct')
    await user.keyboard('{ArrowLeft}')
    expect(screen.getByRole('tooltip')).toHaveTextContent('09 Oct')
    await user.keyboard('{Home}')
    expect(screen.getByRole('tooltip')).toHaveTextContent('01 Oct')
  })

  it('draws a 2px line and an end marker of at least 8px with a surface ring', () => {
    const { container } = render(<TrendChart points={points} ariaLabel="x" />)
    const line = [...container.querySelectorAll('path')].find((p) => p.getAttribute('stroke-width') === '2')
    expect(line).toBeTruthy()
    const dot = container.querySelector('circle')!
    expect(Number(dot.getAttribute('r')) * 2).toBeGreaterThanOrEqual(8)
    expect(dot.getAttribute('stroke-width')).toBe('2')
  })
})

describe('ChartCard table twin', () => {
  it('swaps the plot for a table with the same numbers and back again', async () => {
    const user = userEvent.setup()
    render(
      <ChartCard
        title="By category"
        table={<DataTable caption="By category" columns={[{ key: 'c', label: 'Category' }, { key: 'n', label: 'Complaints', numeric: true }]} rows={[{ c: 'Pothole', n: 13 }]} />}
      >
        <div data-testid="plot">plot</div>
      </ChartCard>,
    )
    expect(screen.getByTestId('plot')).toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: 'View as table' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await user.click(toggle)
    expect(screen.queryByTestId('plot')).toBeNull()
    expect(screen.getByRole('table', { name: 'By category' })).toHaveTextContent('Pothole')
    expect(screen.getByRole('table')).toHaveTextContent('13')
    expect(screen.getByRole('button', { name: 'View chart' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'View chart' }))
    expect(screen.getByTestId('plot')).toBeInTheDocument()
  })
})
