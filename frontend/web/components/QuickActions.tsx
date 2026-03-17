'use client'

interface Props {
  onGotIt: () => void
  onHint: () => void
  onFullSolution: () => void
  disabled?: boolean
}

export default function QuickActions({ onGotIt, onHint, onFullSolution, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-2 px-4 pb-3">
      <button
        onClick={onGotIt}
        disabled={disabled}
        className="rounded-full border border-green-700/60 bg-green-950/40 px-3 py-1.5 text-xs text-green-400 hover:bg-green-900/50 transition-colors disabled:opacity-40"
      >
        I got it! ✓
      </button>
      <button
        onClick={onHint}
        disabled={disabled}
        className="rounded-full border border-amber-700/60 bg-amber-950/40 px-3 py-1.5 text-xs text-amber-400 hover:bg-amber-900/50 transition-colors disabled:opacity-40"
      >
        Still stuck, give me a hint
      </button>
      <button
        onClick={onFullSolution}
        disabled={disabled}
        className="rounded-full border border-blue-700/60 bg-blue-950/40 px-3 py-1.5 text-xs text-blue-400 hover:bg-blue-900/50 transition-colors disabled:opacity-40"
      >
        Show full solution
      </button>
    </div>
  )
}
