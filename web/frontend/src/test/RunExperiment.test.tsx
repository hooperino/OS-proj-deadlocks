import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RunExperiment } from '../pages/RunExperiment'

const closeMock = vi.fn()
vi.mock('../lib/api', () => ({
  api: {
    startExperiment: vi.fn(() => Promise.resolve({ job_id: 'abc123', total: 180 })),
  },
  streamExperiment: vi.fn(() => closeMock),
}))

describe('RunExperiment', () => {
  it('shows the idle start screen, then a running state once started', async () => {
    render(
      <MemoryRouter>
        <RunExperiment />
      </MemoryRouter>,
    )
    expect(screen.getByText('Ready to run the full comparison')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /start experiment/i }))

    await waitFor(() => expect(screen.getByText(/Running/)).toBeInTheDocument())
    expect(screen.getByText('Live run log')).toBeInTheDocument()
  })
})
