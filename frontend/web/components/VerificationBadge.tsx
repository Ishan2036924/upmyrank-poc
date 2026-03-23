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
      <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm">
        <div className="flex items-center gap-2 text-amber-700">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span className="font-medium text-xs">
            Flagged for review · Confidence: {conf}% · Method: {method}
          </span>
        </div>
        {verification.errors && verification.errors.length > 0 && (
          <ul className="mt-1.5 ml-6 space-y-0.5 text-amber-600 text-xs">
            {verification.errors.map((e, i) => (
              <li key={i}>• {e}</li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  return (
    <div className="mt-3 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 font-medium">
      <CheckCircle className="h-4 w-4 flex-shrink-0" />
      <span>Verified · Confidence: {conf}% · Method: {method}</span>
    </div>
  )
}
