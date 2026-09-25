import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Compare } from '../pages/Compare'
import { mockExperimentDetail, mockExperimentList } from './fixtures'

vi.mock('../lib/api', () => ({
  api: {
    experiments: vi.fn(() => Promise.resolve(mockExperimentList)),
    experiment: vi.fn(() => Promise.resolve(mockExperimentDetail)),
  },
}))

describe('Compare', () => {
  it('renders every required metric chart and the cost-profile radars', async () => {
    render(
      <MemoryRouter>
        <Compare />
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByText('Throughput')).toBeInTheDocument())
    expect(screen.getByText('Average waiting time')).toBeInTheDocument()
    expect(screen.getByText('Unnecessary denials')).toBeInTheDocument()
    expect(screen.getByText('Deadlock episodes')).toBeInTheDocument()
    expect(screen.getByText('Recovery actions')).toBeInTheDocument()
    expect(screen.getByText('Useful work lost')).toBeInTheDocument()
    expect(screen.getByText('Cost profile')).toBeInTheDocument()
    expect(screen.getByText('Light contention')).toBeInTheDocument()
    expect(screen.getByText('Heavy contention')).toBeInTheDocument()
  })
})
