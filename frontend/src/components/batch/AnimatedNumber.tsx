import { useEffect, useRef, useState } from 'react'

interface AnimatedNumberProps {
  value: number
  format: (value: number) => string
  /** Milliseconds. Kept short — this must read as instant, not as an animation. */
  duration?: number
  className?: string
}

/**
 * Tweens between two figures so a judge sees the number MOVE rather than swap.
 *
 * Respects `prefers-reduced-motion`: falls straight to the final value, because on a
 * projector a motion-sensitive viewer should still be able to read the simulator.
 */
export function AnimatedNumber({ value, format, duration = 320, className = '' }: AnimatedNumberProps) {
  const [display, setDisplay] = useState(value)
  const fromRef = useRef(value)
  const frameRef = useRef<number>()

  useEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const from = fromRef.current
    const delta = value - from

    if (reduced || delta === 0) {
      fromRef.current = value
      setDisplay(value)
      return
    }

    const start = performance.now()

    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      // easeOutCubic — fast off the mark, settles cleanly.
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(from + delta * eased)
      if (t < 1) {
        frameRef.current = requestAnimationFrame(step)
      } else {
        fromRef.current = value
      }
    }

    frameRef.current = requestAnimationFrame(step)
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
      fromRef.current = value
    }
  }, [value, duration])

  return <span className={`tabular-nums ${className}`}>{format(display)}</span>
}
