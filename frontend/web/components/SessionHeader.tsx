'use client'

import { useEffect, useState } from 'react'

interface Props {
  startedAt: string
  doubtCount: number
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

export default function SessionHeader({ startedAt, doubtCount }: Props) {
  const [elapsed, setElapsed] = useState('')

  useEffect(() => {
    const start = new Date(startedAt).getTime()
    const tick = () => { setElapsed(formatElapsed(Date.now() - start)) }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [startedAt])

  return (
    <div className="flex items-center gap-3 px-6 py-2.5 border-b border-slate-100 text-xs text-slate-500">
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        <span className="font-medium text-slate-700">Study session</span>
        <span>· {elapsed}</span>
      </span>
      <span className="text-slate-300">|</span>
      <span>{doubtCount} doubt{doubtCount !== 1 ? 's' : ''} asked</span>
    </div>
  )
}
