import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Explore } from '../pages/Explore'
import { mockAggregate, mockExperimentList, mockSingleRunResult } from './fixtures'

vi.mock('../lib/api', () => ({
  api: {
    experiments: vi.fn(() => Promise.resolve(mockExperimentList)),
    aggregate: vi.fn(() => Promise.resolve(mockAggregate)),
    rawRun: vi.fn(() => Promise.resolve(mockSingleRunResult)),
    plotUrl: vi.fn((id: string, name: string) => `/api/experiments/${id}/plots/${name}`),
  },
}))

describe('Explore', () => {
  it('lists real runs in a table and opens a drill-down on click', async () => {
    render(
      <MemoryRouter>
        <Explore />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('1 runs')).toBeInTheDocument())
    const seedCell = screen.getByText('101')
    fireEvent.click(seedCell.closest('tr')!)

    await waitFor(() => expect(screen.getAllByText('Ticks elapsed').length).toBeGreaterThan(0))
  })

  it('filters by condition without crashing', async () => {
    render(
      <MemoryRouter>
        <Explore />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('1 runs')).toBeInTheDocument())
    fireEvent.change(screen.getByDisplayValue('All conditions'), { target: { value: 'light' } })
    await waitFor(() => expect(screen.getByText('0 runs')).toBeInTheDocument())
  })
})
