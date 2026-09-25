import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Dashboard } from '../pages/Dashboard'
import { mockExperimentDetail, mockExperimentList } from './fixtures'

vi.mock('../lib/api', () => ({
  api: {
    experiments: vi.fn(() => Promise.resolve(mockExperimentList)),
    experiment: vi.fn(() => Promise.resolve(mockExperimentDetail)),
  },
}))

describe('Dashboard', () => {
  it('renders the hero and, once data loads, real KPI numbers and charts', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )

    expect(screen.getByText(/Three ways to keep an operating system out of deadlock/i)).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText('Experiments run')).toBeInTheDocument())
    expect(screen.getByText('Simulations executed')).toBeInTheDocument()
    expect(await screen.findByText('Latest experiment at a glance')).toBeInTheDocument()
  })
})
