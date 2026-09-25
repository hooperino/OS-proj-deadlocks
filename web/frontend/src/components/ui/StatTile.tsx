import { useEffect, useRef, useState } from 'react'

export function StatTile({
  label,
  value,
  suffix,
  hint,
  color,
}: {
  label: string
  value: React.ReactNode
  suffix?: string
  hint?: string
  color?: string
}) {
  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4">
      <div className="text-[12px] text-(--color-text-muted)">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1 font-mono text-[26px] font-semibold" style={color ? { color } : undefined}>
        {value}
        {suffix && <span className="text-[13px] font-normal text-(--color-text-faint)">{suffix}</span>}
      </div>
      {hint && <div className="mt-1 text-[11.5px] text-(--color-text-faint)">{hint}</div>}
    </div>
  )
}

/** Counts a number up from 0 to `value` once on mount -- the dashboard's
 * one deliberate load-time motion moment, not repeated on every render. */
export function CountUp({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(0)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    const duration = 700
    const start = performance.now()
    let raf: number
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(value * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])

  return <>{display.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}</>
}
