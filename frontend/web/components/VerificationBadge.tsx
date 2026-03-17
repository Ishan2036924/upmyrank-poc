'use client'

import { CheckCircle, AlertTriangle } from 'lucide-react'
import { VerificationResult } from '@/lib/types'

interface Props {
  verification: VerificationResult
}

export default function VerificationBadge({ verification }: Props) {
  const conf = Math.round((verification.confidence || 0) * 100)
  const method = verification.method || 'llm'

  if (verification.flagged_for_review) {
    return (
      <div className="mt-2 rounded-lg border border-amber-700/50 bg-amber-950/40 px-3 py-2 text-sm">
        <div className="flex items-center gap-2 text-amber-400">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span className="font-medium">
            Flagged for review · Confidence: {conf}% · Method: {method}
          </span>
        </div>
        {verification.errors && verification.errors.length > 0 && (
          <ul className="mt-1.5 ml-6 space-y-0.5 text-amber-300/80 text-xs">
            {verification.errors.map((e, i) => (
              <li key={i}>• {e}</li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  return (
    <div className="mt-2 flex items-center gap-2 rounded-lg border border-green-700/50 bg-green-950/40 px-3 py-2 text-sm text-green-400">
      <CheckCircle className="h-4 w-4 flex-shrink-0" />
      <span className="font-medium">
        Verified · Confidence: {conf}% · Method: {method}
      </span>
    </div>
  )
}
