'use client'

interface Props {
  onGotIt: () => void
  onHint: () => void
  onFullSolution: () => void
  disabled?: boolean
}

export default function QuickActions({ onGotIt, onHint, onFullSolution, disabled }: Props) {
  return (
    <div className="flex flex-wrap gap-2 px-1 pb-3">
      <button
        onClick={onGotIt}
        disabled={disabled}
        className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-40"
      >
        I got it! ✓
      </button>
      <button
        onClick={onHint}
        disabled={disabled}
        className="rounded-full border border-amber-200 bg-amber-50 px-4 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100 transition-colors disabled:opacity-40"
      >
        Still stuck, give me a hint
      </button>
      <button
        onClick={onFullSolution}
        disabled={disabled}
        className="rounded-full border border-blue-200 bg-blue-50 px-4 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors disabled:opacity-40"
      >
        Show full solution
      </button>
    </div>
  )
}
