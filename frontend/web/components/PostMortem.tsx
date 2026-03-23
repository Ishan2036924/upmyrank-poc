'use client'

import Link from 'next/link'
import { CheckCircle, XCircle } from 'lucide-react'
import MathText from './MathText'
import { Problem, SubmitResult } from '@/lib/types'

interface QuestionRecord {
  problem: Problem
  result: SubmitResult | null
  answer: string
  timeTaken: number
}

interface Props {
  records: QuestionRecord[]
  onRetake: () => void
  onPracticeWeak: () => void
}

function topicAccuracy(records: QuestionRecord[]): Record<string, { correct: number; total: number }> {
  const acc: Record<string, { correct: number; total: number }> = {}
  for (const r of records) {
    if (!r.result) continue
    const t = r.problem.subtopic || r.problem.topic || 'Unknown'
    if (!acc[t]) acc[t] = { correct: 0, total: 0 }
    acc[t].total++
    if (r.result.correct) acc[t].correct++
  }
  return acc
}

export default function PostMortem({ records, onRetake, onPracticeWeak }: Props) {
  const attempted = records.filter((r) => r.result !== null)
  const correct = attempted.filter((r) => r.result?.correct)
  const avgTime = attempted.length
    ? Math.round(attempted.reduce((s, r) => s + r.timeTaken, 0) / attempted.length) : 0
  const accuracy = attempted.length ? Math.round((correct.length / attempted.length) * 100) : 0
  const topicAcc = topicAccuracy(records)

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 mb-1">Test Complete!</h1>
        <p className="text-slate-400 text-sm">Here&apos;s how you did:</p>
      </div>

      {/* Score cards */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-4 text-center">
          <div className="text-2xl font-bold text-slate-800">{correct.length}/{records.length}</div>
          <div className="text-xs text-slate-400 mt-1">Score</div>
        </div>
        <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-4 text-center">
          <div className="text-2xl font-bold" style={{ color: accuracy >= 70 ? '#22C55E' : accuracy >= 50 ? '#F59E0B' : '#EF4444' }}>
            {accuracy}%
          </div>
          <div className="text-xs text-slate-400 mt-1">Accuracy</div>
        </div>
        <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-4 text-center">
          <div className="text-2xl font-bold text-slate-800">{avgTime}s</div>
          <div className="text-xs text-slate-400 mt-1">Avg time</div>
        </div>
        <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-4 text-center">
          <div className="text-2xl font-bold text-indigo-500">
            {accuracy >= 90 ? 'A+' : accuracy >= 75 ? 'B' : accuracy >= 60 ? 'C' : 'D'}
          </div>
          <div className="text-xs text-slate-400 mt-1">Rank est.</div>
        </div>
      </div>

      {/* Topic breakdown */}
      {Object.keys(topicAcc).length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Topic breakdown</h2>
          <div className="space-y-2">
            {Object.entries(topicAcc).map(([topic, { correct, total }]) => {
              const pct = Math.round((correct / total) * 100)
              const cls = pct >= 70
                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                : pct >= 50
                ? 'bg-amber-50 border-amber-200 text-amber-700'
                : 'bg-red-50 border-red-200 text-red-700'
              return (
                <div key={topic} className={`flex justify-between items-center rounded-xl border px-4 py-2.5 text-sm font-medium ${cls}`}>
                  <span>{topic}</span>
                  <span>{correct}/{total} ({pct}%)</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Answer review */}
      <div>
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Review answers</h2>
        <div className="space-y-2">
          {records.map((r, i) => (
            <div key={i} className="bg-white/80 backdrop-blur-md border border-white/60 rounded-xl px-4 py-3 shadow-sm">
              <div className="flex items-start gap-2">
                {r.result?.correct
                  ? <CheckCircle className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                  : <XCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                }
                <div className="min-w-0 text-sm">
                  <div className="text-slate-800"><MathText>{r.problem?.question_text ?? '—'}</MathText></div>
                  {r.result && !r.result.correct && (
                    <div className="text-xs text-slate-400 mt-1">
                      Correct: <MathText>{r.result.verified_answer}</MathText>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={onPracticeWeak}
          className="rounded-xl bg-indigo-600 hover:bg-indigo-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors"
        >
          Practice weak areas
        </button>
        <button
          onClick={onRetake}
          className="rounded-xl border border-slate-200 hover:bg-slate-50 px-5 py-2.5 text-sm text-slate-600 font-medium transition-colors"
        >
          Take another test
        </button>
        <Link href="/" className="rounded-xl border border-slate-200 hover:bg-slate-50 px-5 py-2.5 text-sm text-slate-500 transition-colors">
          Home
        </Link>
      </div>
    </div>
  )
}
