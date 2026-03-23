'use client'

import { motion } from 'framer-motion'
import MathText from './MathText'
import VerificationBadge from './VerificationBadge'
import { ChatMessage as ChatMessageType } from '@/lib/types'

interface Props {
  message: ChatMessageType
  dimmed?: boolean
}

const MENTOR_MODE_META: Record<string, { icon: string; label: string; cls: string }> = {
  COACH:      { icon: '🏋️', label: 'Coach',      cls: 'bg-emerald-50 border-emerald-200 text-emerald-700' },
  TASKMASTER: { icon: '⚡',  label: 'Taskmaster', cls: 'bg-amber-50 border-amber-200 text-amber-700' },
  COUNSELOR:  { icon: '🧘',  label: 'Counselor',  cls: 'bg-violet-50 border-violet-200 text-violet-700' },
  STRATEGIST: { icon: '🎯',  label: 'Strategist', cls: 'bg-blue-50 border-blue-200 text-blue-700' },
}

const HINT_LABELS: Record<number, string> = {
  1: 'Conceptual hint',
  2: 'Structural hint',
  3: 'Partial solution',
}

export default function ChatMessage({ message, dimmed = false }: Props) {
  const { role, content, metadata } = message

  // ── Divider ───────────────────────────────────────────────────────────────
  if (role === 'divider') {
    const num = metadata?.doubt_block_number ?? '?'
    const topic = metadata?.doubt_block_topic ?? 'Physics'
    const solved = metadata?.doubt_block_solved
    return (
      <div className="flex items-center gap-3 my-5 px-2">
        <div className="flex-1 h-px bg-slate-200" />
        <span className="text-xs text-slate-400 whitespace-nowrap font-medium">
          Doubt {num} · {topic}
          {solved && <span className="ml-1 text-emerald-500"> · ✓ Solved</span>}
        </span>
        <div className="flex-1 h-px bg-slate-200" />
      </div>
    )
  }

  const isStudent = role === 'student'
  const isHint = metadata?.hint_level != null
  const isFull = metadata?.is_full_solution
  const isOutOfScope = metadata?.out_of_scope
  const mentorMeta = metadata?.mentor_mode ? MENTOR_MODE_META[metadata.mentor_mode] : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex mb-4 ${isStudent ? 'justify-end' : 'justify-start'} ${dimmed ? 'opacity-50' : ''}`}
    >
      {/* AI avatar */}
      {!isStudent && (
        <div className="flex-shrink-0 w-8 h-8 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white flex items-center justify-center text-[10px] font-bold mr-3 mt-1 shadow-md shadow-indigo-200">
          AI
        </div>
      )}

      <div className={`max-w-[76%] ${isStudent ? '' : 'flex-1'}`}>
        {/* Top badges — AI only */}
        {!isStudent && (
          <div className="flex flex-wrap gap-1.5 mb-1.5">
            {mentorMeta && (
              <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${mentorMeta.cls}`}>
                <span>{mentorMeta.icon}</span>
                {mentorMeta.label}
              </span>
            )}
            {isHint && !isFull && (
              <span className="inline-block rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-xs font-medium px-2.5 py-0.5">
                Hint {metadata!.hint_level} · {HINT_LABELS[metadata!.hint_level!] ?? 'Hint'}
              </span>
            )}
            {isFull && (
              <span className="inline-block rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium px-2.5 py-0.5">
                ✓ Full Solution
              </span>
            )}
            {isOutOfScope && (
              <span className="inline-block rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-xs font-medium px-2.5 py-0.5">
                ⚠ Outside syllabus scope
              </span>
            )}
          </div>
        )}

        {/* Message bubble */}
        {isStudent ? (
          <div className="bg-slate-900 text-white rounded-3xl rounded-br-lg px-5 py-3.5 text-sm leading-relaxed shadow-lg shadow-slate-900/15">
            <MathText>{content}</MathText>
          </div>
        ) : (
          <div className="bg-white text-slate-800 rounded-3xl rounded-bl-lg px-5 py-3.5 text-sm leading-relaxed shadow-sm shadow-slate-200/80 border border-slate-100">
            <MathText>{content}</MathText>
            {metadata?.verification && (
              <VerificationBadge verification={metadata.verification} />
            )}
          </div>
        )}

        {/* Subtopic label */}
        {!isStudent && metadata?.analysis && (
          <div className="mt-1 text-xs text-slate-400 pl-1">
            {(metadata.analysis as { subtopic?: string }).subtopic
              ? `Topic: ${(metadata.analysis as { subtopic: string }).subtopic}`
              : ''}
          </div>
        )}
      </div>
    </motion.div>
  )
}
