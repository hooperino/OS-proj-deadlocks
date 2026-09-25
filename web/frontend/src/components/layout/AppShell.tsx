import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import { Sidebar } from './Sidebar'

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-(--color-void) text-(--color-text)">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-(--color-border) bg-(--color-panel) md:block">
        <Sidebar />
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-(--color-border) bg-(--color-panel)/95 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center gap-2 font-semibold text-[15px]">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <circle cx="6" cy="6" r="3.2" stroke="var(--color-prevention)" strokeWidth="1.6" />
            <circle cx="18" cy="6" r="3.2" stroke="var(--color-avoidance)" strokeWidth="1.6" />
            <circle cx="12" cy="17" r="3.2" stroke="var(--color-recovery)" strokeWidth="1.6" />
          </svg>
          Deadlock Lab
        </div>
        <button
          aria-label="Open navigation"
          onClick={() => setMobileOpen(true)}
          className="rounded-md p-1.5 text-(--color-text-muted) hover:bg-(--color-panel-raised)"
        >
          <Menu size={20} />
        </button>
      </header>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/60 md:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-64 bg-(--color-panel) shadow-2xl md:hidden"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
            >
              <button
                aria-label="Close navigation"
                onClick={() => setMobileOpen(false)}
                className="absolute right-3 top-4 rounded-md p-1.5 text-(--color-text-muted) hover:bg-(--color-panel-raised)"
              >
                <X size={18} />
              </button>
              <Sidebar onNavigate={() => setMobileOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <main className="md:pl-60">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 md:px-8 md:py-10">{children}</div>
      </main>
    </div>
  )
}
