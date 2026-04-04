'use client'

import { RotateCcw, AlertCircle } from 'lucide-react'

interface Props {
  error: string
  onRetry: () => void
}

/**
 * Glassmorphic error card shown when an API call fails or a render error
 * is caught by ErrorBoundary.  "Try Again" re-fires the last message.
 */
export default function ChatErrorFallback({ error, onRetry }: Props) {
  // Strip JSON wrapper from FastAPI error strings if present
  let message = error
  try {
    const parsed = JSON.parse(error)
    message = parsed.detail ?? error
  } catch { /* not JSON */ }

  return (
    <div className="flex justify-start mb-5">
      <div className="max-w-[76%] bg-red-50/80 backdrop-blur-sm border border-red-100 rounded-3xl rounded-tl-md px-5 py-4 shadow-[0_4px_20px_rgb(239,68,68,0.06)]">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
          <span className="text-xs font-semibold text-red-500 uppercase tracking-wider">
            Something went wrong
          </span>
        </div>
        <p className="text-sm text-slate-600 leading-relaxed mb-3 break-words">
          {message.length > 200 ? message.slice(0, 200) + '…' : message}
        </p>
        <button
          onClick={onRetry}
          className="flex items-center gap-2 rounded-full border border-red-200 bg-white hover:bg-red-50 px-4 py-1.5 text-xs font-medium text-red-600 transition-all duration-300 ease-out hover:scale-[1.02] active:scale-[0.98] shadow-sm"
        >
          <RotateCcw className="h-3 w-3" />
          Try again
        </button>
      </div>
    </div>
  )
}
