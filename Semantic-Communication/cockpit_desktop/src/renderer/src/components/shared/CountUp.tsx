/**
 * CountUp animation component for numbers
 * Animates from the last rendered value to the next target value with easing
 */
import { useState, useEffect, useRef } from 'react'
import { T } from '../../theme/tokens'

interface CountUpProps {
  end: number
  duration?: number
  decimals?: number
  className?: string
  formatValue?: (value: number) => string
}

export function CountUp({
  end,
  duration = T.durationNormal,
  decimals = 0,
  className = '',
  formatValue,
}: CountUpProps) {
  const [current, setCurrent] = useState(0)
  const startTime = useRef<number>()
  const requestRef = useRef<number>()
  const valueRef = useRef(0)

  useEffect(() => {
    if (end === null || end === undefined || Number.isNaN(end)) {
      valueRef.current = 0
      setCurrent(0)
      return
    }

    const startValue = valueRef.current
    const delta = end - startValue

    if (delta === 0) {
      startTime.current = undefined
      valueRef.current = end
      setCurrent(end)
      return
    }

    const animate = (timestamp: number) => {
      if (!startTime.current) startTime.current = timestamp
      const progress = timestamp - startTime.current
      const percent = Math.min(progress / duration, 1)

      // Easing: ease-out cubic
      const eased = 1 - Math.pow(1 - percent, 3)
      const nextValue = startValue + delta * eased

      valueRef.current = nextValue
      setCurrent(nextValue)

      if (percent < 1) {
        requestRef.current = requestAnimationFrame(animate)
      } else {
        startTime.current = undefined
        valueRef.current = end
        setCurrent(end)
      }
    }

    startTime.current = undefined
    requestRef.current = requestAnimationFrame(animate)

    return () => {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current)
      }
      requestRef.current = undefined
      startTime.current = undefined
    }
  }, [end, duration])

  const displayValue = formatValue ? formatValue(current) : current.toFixed(decimals)

  return <span className={className}>{displayValue}</span>
}
