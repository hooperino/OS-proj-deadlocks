import { ChevronDown } from 'lucide-react'
import type { ExperimentListItem } from '../lib/types'
import { formatTimestamp } from '../lib/format'

export function ExperimentPicker({
  experiments,
  value,
  onChange,
}: {
  experiments: ExperimentListItem[]
  value: string | null
  onChange: (id: string) => void
}) {
  return (
    <div className="relative">
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-md border border-(--color-border-strong) bg-(--color-panel-raised) py-2 pl-3 pr-9 text-[12.5px] text-(--color-text) outline-none"
      >
        {experiments.map((e, i) => (
          <option key={e.id} value={e.id}>
            {i === 0 ? 'Latest \u2014 ' : ''}
            {formatTimestamp(e.timestamp)}
            {e.incomplete_runs ? ` (${e.incomplete_runs} incomplete)` : ''}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-(--color-text-faint)" />
    </div>
  )
}
