import { NavLink } from 'react-router-dom'
import { GitCompareArrows, LayoutDashboard, Play, SearchCode, Target } from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/compare', label: 'Compare strategies', icon: GitCompareArrows },
  { to: '/run', label: 'Run experiment', icon: Play },
  { to: '/single-run', label: 'Single run', icon: Target },
  { to: '/explore', label: 'Explore results', icon: SearchCode },
]

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-2.5">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="shrink-0">
            <circle cx="6" cy="6" r="3.2" stroke="var(--color-prevention)" strokeWidth="1.6" />
            <circle cx="18" cy="6" r="3.2" stroke="var(--color-avoidance)" strokeWidth="1.6" />
            <circle cx="12" cy="17" r="3.2" stroke="var(--color-recovery)" strokeWidth="1.6" />
            <path d="M8.6 7.8 L15.4 7.8" stroke="var(--color-text-faint)" strokeWidth="1.4" />
            <path d="M7.4 8.6 L10.6 14.6" stroke="var(--color-text-faint)" strokeWidth="1.4" />
            <path d="M16.6 8.6 L13.4 14.6" stroke="var(--color-text-faint)" strokeWidth="1.4" />
          </svg>
          <div className="leading-tight">
            <div className="font-semibold tracking-tight text-[15px]">Deadlock Lab</div>
            <div className="text-[11px] text-(--color-text-faint)">Prevention, Avoidance & Recovery</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-3">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-2.5 rounded-md px-3 py-2 text-[13.5px] transition-colors',
                isActive
                  ? 'bg-(--color-amber-soft) text-(--color-amber)'
                  : 'text-(--color-text-muted) hover:bg-(--color-panel-raised) hover:text-(--color-text)',
              )
            }
          >
            <item.icon size={16} strokeWidth={1.9} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-(--color-border) px-5 py-4 text-[11px] text-(--color-text-faint) leading-relaxed">
        20 processes, 5 resources.
        <br />
        180 runs per full experiment.
      </div>
    </div>
  )
}
