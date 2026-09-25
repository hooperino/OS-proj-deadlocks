import '@testing-library/jest-dom/vitest'

// jsdom has no ResizeObserver, which Recharts' ResponsiveContainer needs.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// @ts-expect-error -- test shim
global.ResizeObserver = ResizeObserverStub

// jsdom has no EventSource; RunExperiment imports it at module scope.
class EventSourceStub {
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  close() {}
}
// @ts-expect-error -- test shim
global.EventSource = EventSourceStub
