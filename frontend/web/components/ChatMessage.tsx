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
  COACH:      { icon: '🏋️', label: 'Coach',      cls: 'bg-green-900/60 border-green-700/50 text-green-300' },
  TASKMASTER: { icon: '⚡',  label: 'Taskmaster', cls: 'bg-amber-900/60 border-amber-700/50 text-amber-300' },
  COUNSELOR:  { icon: '🧘',  label: 'Counselor',  cls: 'bg-purple-900/60 border-purple-700/50 text-purple-300' },
  STRATEGIST: { icon: '🎯',  label: 'Strategist', cls: 'bg-blue-900/60 border-blue-700/50 text-blue-300' },
}

const HINT_LABELS: Record<number, string> = {
  1: 'Conceptual hint',
  2: 'Structural hint',
  3: 'Partial solution',
}

export default function ChatMessage({ message, dimmed = false }: Props) {
  const { role, content, metadata } = message

  // ── Divider rendering ───────────────────────────────────────────────────
  if (role === 'divider') {
    const num = metadata?.doubt_block_number ?? '?'
    const topic = metadata?.doubt_block_topic ?? 'Physics'
    const solved = metadata?.doubt_block_solved
    return (
      <div className="flex items-center gap-3 my-4 px-2">
        <div className="flex-1 h-px bg-gray-700" />
        <span className="text-xs text-gray-500 whitespace-nowrap">
          Doubt {num} &middot; {topic}
          {solved && <span className="ml-1 text-green-500"> &middot; &#10003; Solved</span>}
        </span>
        <div className="flex-1 h-px bg-gray-700" />
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
      className={`flex mb-4 ${isStudent ? 'justify-end' : 'justify-start'} ${dimmed ? 'opacity-60' : ''}`}
    >
      {/* AI avatar */}
      {!isStudent && (
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-green-900 text-green-400 flex items-center justify-center text-xs font-bold mr-3 mt-1">
          AI
        </div>
      )}

      <div className={`max-w-[78%] ${isStudent ? '' : 'flex-1'}`}>
        {/* Top badges row (AI messages only) */}
        {!isStudent && (
          <div className="flex flex-wrap gap-1.5 mb-1.5">
            {mentorMeta && (
              <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs ${mentorMeta.cls}`}>
                <span>{mentorMeta.icon}</span>
                {mentorMeta.label}
              </span>
            )}
            {isHint && !isFull && (
              <span className="inline-block rounded-full bg-amber-900/60 border border-amber-700/50 text-amber-300 text-xs px-2.5 py-0.5">
                Hint {metadata!.hint_level} · {HINT_LABELS[metadata!.hint_level!] ?? 'Hint'}
              </span>
            )}
            {isFull && (
              <span className="inline-block rounded-full bg-green-900/60 border border-green-700/50 text-green-300 text-xs px-2.5 py-0.5">
                ✓ Full Solution
              </span>
            )}
            {isOutOfScope && (
              <span className="inline-block rounded-full bg-amber-900/60 border border-amber-700/50 text-amber-300 text-xs px-2.5 py-0.5">
                ⚠ Outside syllabus scope
              </span>
            )}
          </div>
        )}

        {/* Message bubble */}
        {isStudent ? (
          <div className="bg-blue-600/20 text-blue-100 rounded-2xl rounded-br-sm px-4 py-3 text-sm leading-relaxed">
            <MathText>{content}</MathText>
          </div>
        ) : (
          <div className="bg-gray-800 text-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 text-sm leading-relaxed">
            <MathText>{content}</MathText>
            {metadata?.verification && (
              <VerificationBadge verification={metadata.verification} />
            )}
          </div>
        )}

        {/* Topic label below AI bubble */}
        {!isStudent && metadata?.analysis && (
          <div className="mt-1 text-xs text-gray-500">
            {(metadata.analysis as { subtopic?: string }).subtopic
              ? `Topic: ${(metadata.analysis as { subtopic: string }).subtopic}`
              : ''}
          </div>
        )}
      </div>
    </motion.div>
  )
}
