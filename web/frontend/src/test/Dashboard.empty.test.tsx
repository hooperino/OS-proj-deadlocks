import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Dashboard } from '../pages/Dashboard'

vi.mock('../lib/api', () => ({
  api: {
    experiments: vi.fn(() => Promise.resolve([])),
    experiment: vi.fn(() => Promise.reject(new Error('no experiments'))),
  },
}))

describe('Dashboard with no experiments yet', () => {
  it('shows an honest empty state instead of fake data', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    )
    expect(await screen.findByText(/No experiments have been run yet/i)).toBeInTheDocument()
  })
})
