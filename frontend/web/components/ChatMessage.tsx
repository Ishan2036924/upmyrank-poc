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
  COACH:      { icon: '🏋️', label: 'Coach',      cls: 'bg-emerald-50 border-emerald-100 text-emerald-700' },
  TASKMASTER: { icon: '⚡',  label: 'Taskmaster', cls: 'bg-amber-50 border-amber-100 text-amber-700' },
  COUNSELOR:  { icon: '🧘',  label: 'Counselor',  cls: 'bg-violet-50 border-violet-100 text-violet-700' },
  STRATEGIST: { icon: '🎯',  label: 'Strategist', cls: 'bg-blue-50 border-blue-100 text-blue-700' },
}

const HINT_LABELS: Record<number, { label: string; cls: string; icon: string }> = {
  1: { label: 'Conceptual hint',  icon: '💡', cls: 'bg-sky-50 border-sky-100 text-sky-700' },
  2: { label: 'Structural hint',  icon: '🔩', cls: 'bg-indigo-50 border-indigo-100 text-indigo-700' },
  3: { label: 'Forced attempt',   icon: '✍️', cls: 'bg-orange-50 border-orange-100 text-orange-700' },
}

// Ease-out expo — feels premium, snappy
const EASE_OUT_EXPO: [number, number, number, number] = [0.16, 1, 0.3, 1]

export default function ChatMessage({ message, dimmed = false }: Props) {
  const { role, content, metadata } = message

  // ── Divider ───────────────────────────────────────────────────────────────
  if (role === 'divider') {
    const num   = metadata?.doubt_block_number ?? '?'
    const topic = metadata?.doubt_block_topic  ?? 'Physics'
    const solved = metadata?.doubt_block_solved
    return (
      <motion.div
        initial={{ opacity: 0, scaleX: 0.8 }}
        animate={{ opacity: 1, scaleX: 1 }}
        transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
        className="flex items-center gap-3 my-6 px-2"
      >
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
        <span className="flex items-center gap-1.5 text-xs text-slate-400 whitespace-nowrap font-medium bg-white/70 border border-slate-100 rounded-full px-3 py-1 shadow-sm">
          <span className="text-slate-300">#</span>
          Doubt {num}
          <span className="text-slate-300">·</span>
          {topic}
          {solved && <span className="text-emerald-500 ml-0.5">· ✓</span>}
        </span>
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
      </motion.div>
    )
  }

  const isStudent      = role === 'student'
  const isHint         = metadata?.hint_level != null
  const isFull         = metadata?.is_full_solution
  const isForcedAttempt = metadata?.is_forced_attempt
  const isOutOfScope   = metadata?.out_of_scope
  const mentorMeta     = metadata?.mentor_mode ? MENTOR_MODE_META[metadata.mentor_mode] : null
  const hintMeta       = isHint && !isFull && metadata?.hint_level != null
    ? HINT_LABELS[metadata.hint_level!]
    : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
      className={`flex mb-5 ${isStudent ? 'justify-end' : 'justify-start'} ${dimmed ? 'opacity-40 pointer-events-none' : ''}`}
    >
      {/* AI avatar */}
      {!isStudent && (
        <div className="flex-shrink-0 w-9 h-9 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white flex items-center justify-center text-[10px] font-bold mr-3 mt-0.5 shadow-lg shadow-indigo-200/60 ring-2 ring-white">
          AI
        </div>
      )}

      <div className={`max-w-[76%] ${isStudent ? '' : 'flex-1'}`}>

        {/* Badges — AI only */}
        {!isStudent && (mentorMeta || hintMeta || isFull || isForcedAttempt || isOutOfScope) && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {mentorMeta && (
              <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${mentorMeta.cls}`}>
                <span>{mentorMeta.icon}</span>
                {mentorMeta.label}
              </span>
            )}
            {hintMeta && (
              <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${hintMeta.cls}`}>
                <span>{hintMeta.icon}</span>
                Hint {metadata!.hint_level} · {hintMeta.label}
              </span>
            )}
            {isFull && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-700 text-xs font-medium px-2.5 py-0.5">
                ✓ Full Solution
              </span>
            )}
            {isForcedAttempt && !isFull && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-orange-50 border border-orange-100 text-orange-700 text-xs font-semibold px-2.5 py-0.5">
                ✍️ Your turn — attempt required
              </span>
            )}
            {isOutOfScope && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-100 text-amber-700 text-xs font-medium px-2.5 py-0.5">
                ⚠ Outside syllabus
              </span>
            )}
          </div>
        )}

        {/* Bubble */}
        {isStudent ? (
          /* Student — dark pill */
          <div className="bg-slate-900 text-white rounded-3xl rounded-br-md px-5 py-3.5 text-sm leading-relaxed shadow-[0_4px_20px_rgb(15,23,42,0.18)]">
            <MathText>{content}</MathText>
            {metadata?.confidence && (
              <div className="mt-2.5 pt-2.5 border-t border-white/10 flex items-center gap-1.5">
                <span className="text-[11px] text-white/50 leading-none">
                  {metadata.confidence === 'low'
                    ? '🔴 Taking a guess'
                    : metadata.confidence === 'medium'
                    ? '🟡 Somewhat sure'
                    : '🟢 100% Confident'}
                </span>
              </div>
            )}
          </div>
        ) : (
          /* AI — frameless, clean body text */
          <div className={`text-slate-800 text-sm leading-relaxed px-1 ${isForcedAttempt && !isFull ? 'border-l-2 border-orange-300 pl-4' : ''}`}>
            <MathText>{content}</MathText>
            {metadata?.verification && (
              <div className="mt-3">
                <VerificationBadge verification={metadata.verification} />
              </div>
            )}
          </div>
        )}

        {/* Subtopic tag — AI only */}
        {!isStudent && metadata?.analysis && (
          <div className="mt-1.5 text-xs text-slate-400 pl-1">
            {(metadata.analysis as { subtopic?: string }).subtopic
              ? `${(metadata.analysis as { subtopic: string }).subtopic}`
              : ''}
          </div>
        )}
      </div>
    </motion.div>
  )
}
