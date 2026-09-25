import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SingleRun } from '../pages/SingleRun'
import { mockConfig, mockSingleRunResult } from './fixtures'

vi.mock('../lib/api', () => ({
  api: {
    config: vi.fn(() => Promise.resolve(mockConfig)),
    singleRun: vi.fn(() => Promise.resolve(mockSingleRunResult)),
  },
}))

describe('SingleRun', () => {
  it('runs a live simulation on click and displays the real result', async () => {
    render(
      <MemoryRouter>
        <SingleRun />
      </MemoryRouter>,
    )
    const runButton = await screen.findByRole('button', { name: /^run$/i })
    fireEvent.click(runButton)

    await waitFor(() => expect(screen.getByText('Ticks elapsed')).toBeInTheDocument())
    expect(screen.getByText('180')).toBeInTheDocument() // ticks_elapsed from the mock result
    expect(screen.getByText('Resource utilization')).toBeInTheDocument()
    expect(screen.getByText('Algorithm overhead')).toBeInTheDocument()
  })
})
