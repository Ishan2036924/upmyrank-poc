'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import {
  MessageCircle, Target, Timer, BarChart3,
  ChevronRight, Sparkles, CalendarDays, RotateCcw,
  Atom, FlaskConical, Calculator,
} from 'lucide-react'
import Sidebar from '@/components/Sidebar'
import { apiGet } from '@/lib/api'
import { StudentGenome } from '@/lib/types'
import AuthGuard from '@/components/AuthGuard'
import { useAuth } from '@/lib/auth'
import { SYLLABUS_MAP } from '@/lib/syllabus'

// ── Animation variants ────────────────────────────────────────────────────────

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1]

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
}

const itemVariants = {
  hidden:  { opacity: 0, y: 20, scale: 0.97 },
  visible: { opacity: 1, y: 0,  scale: 1, transition: { duration: 0.5, ease: EASE } },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function masteryColor(m: number): string {
  if (m < 0.3) return '#EF4444'
  if (m < 0.7) return '#F59E0B'
  return '#22C55E'
}

/** Compute average mastery for a given subject by matching topic_mastery keys against known topic names */
function computeSubjectMastery(
  subjectName: 'Physics' | 'Chemistry' | 'Maths',
  topicMastery: Record<string, { average: number; concepts: unknown[] }>,
): number {
  const subject = SYLLABUS_MAP[subjectName]
  if (!subject) return 0
  // Collect all topic names for this subject (lowercase)
  const allTopics = subject.chapters.flatMap((ch) => ch.topics.map((t) => t.name.toLowerCase()))
  const topicMasteryNorm = Object.fromEntries(
    Object.entries(topicMastery).map(([k, v]) => [k.toLowerCase(), v.average])
  )
  const matched: number[] = []
  for (const topic of allTopics) {
    if (topicMasteryNorm[topic] !== undefined) {
      matched.push(topicMasteryNorm[topic])
    }
  }
  if (matched.length === 0) return 0
  return matched.reduce((a, b) => a + b, 0) / matched.length
}

/** Days until JEE Main (approximate: April of target year) */
function daysUntilExam(targetYear: number): number | null {
  if (!targetYear) return null
  // JEE Main is typically held in January & April; use April 1 as proxy
  const examDate = new Date(`${targetYear}-04-01`)
  const today    = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.ceil((examDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : null
}

interface MentorMeta {
  mode: string; icon: string; greeting: string
  accentColor: string; accentBg: string
}

function getMentorMode(genome: StudentGenome): MentorMeta {
  const pct      = Math.round(genome.overall_mastery * 100)
  const sessions = genome.total_sessions
  const w0       = genome.weakest_concepts[0]?.subtopic ?? '—'
  const w1       = genome.weakest_concepts[1]?.subtopic ?? '—'

  if (pct < 25) return {
    mode: 'COUNSELOR', icon: '🧘', accentColor: '#9333EA', accentBg: 'rgba(147,51,234,0.08)',
    greeting: `Hey, no pressure today. You're at ${pct}% — let's take it one concept at a time and build the foundation properly. We'll start with ${w0}.`,
  }
  if (sessions === 0) return {
    mode: 'COACH', icon: '🏋️', accentColor: '#22C55E', accentBg: 'rgba(34,197,94,0.08)',
    greeting: `Welcome! Your knowledge genome is ready. Your current mastery is ${pct}%. Let's start with your weakest area: ${w0}.`,
  }
  if (pct > 60 && sessions > 5) return {
    mode: 'STRATEGIST', icon: '🎯', accentColor: '#3B82F6', accentBg: 'rgba(59,130,246,0.08)',
    greeting: `You're at ${pct}% with ${sessions} sessions done — solid progress. Let's be strategic and close the gaps: focus on ${w0} and ${w1} today.`,
  }
  return {
    mode: 'COACH', icon: '🏋️', accentColor: '#22C55E', accentBg: 'rgba(34,197,94,0.08)',
    greeting: `Good to see you! You're at ${pct}% overall. Today's focus: ${w0} and ${w1}. Let's improve those together.`,
  }
}

// ── Subject card config ───────────────────────────────────────────────────────

const SUBJECT_CARDS = [
  {
    name:    'Physics' as const,
    icon:    Atom,
    color:   'text-blue-600',
    border:  'border-blue-100',
    bg:      'bg-blue-50/60',
    barBg:   'bg-blue-500',
    badge:   'bg-blue-50 border-blue-200 text-blue-700',
    href:    '/doubt?subject=Physics',
  },
  {
    name:    'Chemistry' as const,
    icon:    FlaskConical,
    color:   'text-emerald-600',
    border:  'border-emerald-100',
    bg:      'bg-emerald-50/60',
    barBg:   'bg-emerald-500',
    badge:   'bg-emerald-50 border-emerald-200 text-emerald-700',
    href:    '/doubt?subject=Chemistry',
  },
  {
    name:    'Maths' as const,
    icon:    Calculator,
    color:   'text-violet-600',
    border:  'border-violet-100',
    bg:      'bg-violet-50/60',
    barBg:   'bg-violet-500',
    badge:   'bg-violet-50 border-violet-200 text-violet-700',
    href:    '/doubt?subject=Maths',
  },
]

// ── Action card config ────────────────────────────────────────────────────────

const ACTION_CARDS = [
  {
    icon: MessageCircle, title: 'Ask a doubt',
    desc: "Type a question you're stuck on — I'll guide you step by step, Socratically.",
    href: '/doubt', span: 'col-span-2', accent: 'text-indigo-500',
    accentBg: 'rgba(99,102,241,0.06)',
  },
  {
    icon: Target, title: 'Practice',
    desc: '5 problems picked for your weak areas.',
    href: '/practice', span: 'col-span-1', accent: 'text-emerald-500',
    accentBg: 'rgba(34,197,94,0.06)',
  },
  {
    icon: Timer, title: 'Mock test',
    desc: 'Timed · 10 Qs · Exam conditions',
    href: '/mock', span: 'col-span-1', accent: 'text-amber-500',
    accentBg: 'rgba(245,158,11,0.06)',
  },
  {
    icon: BarChart3, title: 'My progress',
    desc: 'Knowledge genome, study plan, and full analytics.',
    href: '/progress', span: 'col-span-2', accent: 'text-blue-500',
    accentBg: 'rgba(59,130,246,0.06)',
  },
]

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const { studentId } = useAuth()
  const [genome, setGenome] = useState<StudentGenome | null>(null)

  useEffect(() => {
    if (studentId) {
      apiGet(`/student/${studentId}`).then(setGenome).catch(console.error)
    }
  }, [studentId])

  const weakest      = genome?.weakest_concepts ?? []
  const studyPlan    = weakest.slice(0, 3).map((c) => ({
    subtopic: c.subtopic, mastery: c.mastery, problems: 5, time: '15–20 min',
  }))
  const mentor         = genome ? getMentorMode(genome) : null
  const personaSummary = genome?.persona_profile?.persona_summary ?? null
  const daysLeft       = genome?.target_year ? daysUntilExam(genome.target_year) : null
  const examYear       = genome?.target_year ?? null

  return (
    <AuthGuard>
    <div className="flex h-[100dvh]">
      <Sidebar />
      <main className="md:ml-[236px] flex-1 overflow-y-auto pt-14 md:pt-0 scroll-touch">
        <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 pb-6">

          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-5"
          >

            {/* ── Mentor greeting card ──────────────────────────────────── */}
            <motion.div
              variants={itemVariants}
              className="relative rounded-3xl bg-white/80 backdrop-blur-md border border-white/50 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden hover:-translate-y-0.5 hover:shadow-[0_16px_40px_rgb(0,0,0,0.07)] transition-all duration-300 ease-out"
            >
              {/* Accent side stripe */}
              <div
                className="absolute left-0 top-0 bottom-0 w-1 rounded-l-3xl"
                style={{ backgroundColor: mentor?.accentColor ?? '#7C3AED' }}
              />
              {/* Ambient background orb */}
              <div
                className="absolute top-0 left-0 w-64 h-full pointer-events-none"
                style={{ background: `linear-gradient(to right, ${mentor?.accentBg ?? 'rgba(124,58,237,0.06)'}, transparent)` }}
              />
              <div className="relative px-5 md:px-7 py-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xl">{mentor?.icon ?? '🎓'}</span>
                  <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: mentor?.accentColor ?? '#7C3AED' }}>
                    AI Mentor · {mentor?.mode ?? 'Loading…'}
                  </span>
                  <Sparkles className="h-3 w-3 ml-auto" style={{ color: mentor?.accentColor ?? '#7C3AED', opacity: 0.5 }} />
                </div>
                {genome ? (
                  <p className="text-slate-700 leading-relaxed text-sm">
                    {personaSummary ?? mentor?.greeting}
                  </p>
                ) : (
                  <div className="space-y-2">
                    <div className="h-4 bg-slate-100 rounded-full w-3/4 animate-pulse" />
                    <div className="h-4 bg-slate-100 rounded-full w-1/2 animate-pulse" />
                  </div>
                )}
              </div>
            </motion.div>

            {/* ── Subject mastery cards + Exam countdown ───────────────── */}
            <motion.div variants={itemVariants} className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {SUBJECT_CARDS.map((s) => {
                const m   = genome ? computeSubjectMastery(s.name, genome.topic_mastery) : null
                const pct = m !== null ? Math.round(m * 100) : null
                return (
                  <Link key={s.name} href={s.href} className={`group rounded-2xl border ${s.border} ${s.bg} backdrop-blur-sm px-4 py-3.5 flex flex-col gap-2 hover:-translate-y-0.5 hover:shadow-md transition-all duration-200 active:scale-[0.98]`}>
                    <div className="flex items-center gap-2">
                      <s.icon className={`h-4 w-4 ${s.color} flex-shrink-0`} />
                      <span className={`text-xs font-bold ${s.color}`}>{s.name}</span>
                    </div>
                    {pct !== null ? (
                      <>
                        <div className="text-xl font-bold text-slate-800 tabular-nums leading-none">
                          {pct}%
                        </div>
                        <div className="h-1 bg-white/60 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${s.barBg} transition-all duration-700`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-500">
                          {pct < 30 ? 'Needs work' : pct < 70 ? 'Building up' : 'Strong'}
                        </span>
                      </>
                    ) : (
                      <div className="h-4 bg-white/60 rounded-full w-2/3 animate-pulse mt-1" />
                    )}
                  </Link>
                )
              })}

              {/* Exam countdown card */}
              <div className="rounded-2xl border border-rose-100 bg-rose-50/60 backdrop-blur-sm px-4 py-3.5 flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4 text-rose-500 flex-shrink-0" />
                  <span className="text-xs font-bold text-rose-600">Exam</span>
                </div>
                {daysLeft !== null ? (
                  <>
                    <div className="text-xl font-bold text-slate-800 tabular-nums leading-none">
                      {daysLeft}
                    </div>
                    <span className="text-[10px] text-slate-500">days left</span>
                    <span className={`text-[10px] font-semibold ${daysLeft < 90 ? 'text-rose-600' : 'text-slate-400'}`}>
                      JEE {examYear}
                    </span>
                  </>
                ) : (
                  <div className="text-xs text-slate-400 mt-1">Set exam year in settings</div>
                )}
              </div>
            </motion.div>

            {/* ── Continue last session ─────────────────────────────────── */}
            {genome && genome.total_sessions > 0 && (
              <motion.div variants={itemVariants}>
                <Link
                  href="/doubt"
                  className="group flex items-center gap-4 bg-white/80 backdrop-blur-md border border-white/50 shadow-[0_4px_20px_rgb(0,0,0,0.04)] rounded-2xl px-5 py-4 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgb(0,0,0,0.07)] transition-all duration-300 ease-out active:scale-[0.99]"
                >
                  <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-200 transition-colors duration-200">
                    <RotateCcw className="h-4 w-4 text-indigo-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-slate-800">Continue where you left off</div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {genome.total_sessions} session{genome.total_sessions !== 1 ? 's' : ''} · {genome.resolved_sessions} doubt{genome.resolved_sessions !== 1 ? 's' : ''} resolved
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-500 group-hover:translate-x-0.5 transition-all duration-200 flex-shrink-0" />
                </Link>
              </motion.div>
            )}

            {/* ── Bento action cards ────────────────────────────────────── */}
            {/* Desktop: 3-col asymmetric grid. Mobile: 2-col */}
            <motion.div variants={containerVariants} className="grid grid-cols-2 md:grid-cols-3 gap-3 md:gap-4">
              {ACTION_CARDS.map((card) => (
                <motion.div
                  key={card.href}
                  variants={itemVariants}
                  className={`${card.span === 'col-span-2' ? 'md:col-span-2' : ''} col-span-1`}
                >
                  <Link
                    href={card.href}
                    className="group relative flex flex-col h-full bg-white/80 backdrop-blur-md border border-white/50 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-3xl p-5 md:p-6 hover:-translate-y-1 hover:shadow-[0_16px_48px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out active:scale-[0.98] overflow-hidden"
                  >
                    {/* Ambient orb */}
                    <div
                      className="absolute bottom-0 right-0 w-24 h-24 rounded-full translate-x-8 translate-y-8 pointer-events-none transition-all duration-300 group-hover:scale-125"
                      style={{ background: `radial-gradient(circle, ${card.accentBg.replace('0.06', '0.12')} 0%, transparent 70%)` }}
                    />
                    <div className="relative flex-1 flex flex-col">
                      <card.icon className={`h-5 w-5 ${card.accent} mb-3 md:mb-4 transition-transform duration-300 ease-out group-hover:scale-110`} />
                      <div className="font-semibold text-slate-900 text-sm mb-1">{card.title}</div>
                      <div className="text-xs md:text-sm text-slate-500 flex-1 leading-relaxed">{card.desc}</div>
                      <div className={`mt-3 md:mt-4 text-xs font-semibold ${card.accent} flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200`}>
                        Get started <ChevronRight className="h-3 w-3" />
                      </div>
                    </div>
                  </Link>
                </motion.div>
              ))}
            </motion.div>

            {/* ── Today's study plan ────────────────────────────────────── */}
            {studyPlan.length > 0 && (
              <motion.div variants={itemVariants}>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-3">
                  Today&apos;s study plan
                </p>
                <motion.div variants={containerVariants} className="space-y-2.5">
                  {studyPlan.map((item, i) => (
                    <motion.div key={i} variants={itemVariants}>
                      <Link
                        href="/practice"
                        className="group flex items-center gap-4 bg-white/80 backdrop-blur-md border border-white/50 shadow-[0_4px_16px_rgb(0,0,0,0.04)] rounded-2xl px-5 py-3.5 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgb(0,0,0,0.07)] transition-all duration-300 ease-out active:scale-[0.99]"
                      >
                        <div className="w-4 h-4 rounded-full border-2 border-slate-200 flex-shrink-0 group-hover:border-indigo-300 transition-colors duration-200" />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-slate-800 font-medium truncate">{item.subtopic}</div>
                          <div className="text-xs text-slate-400 mt-0.5">{item.problems} problems · {item.time}</div>
                        </div>
                        <div className="flex-shrink-0 flex items-center gap-2">
                          <span className="text-sm font-bold tabular-nums" style={{ color: masteryColor(item.mastery) }}>
                            {Math.round(item.mastery * 100)}%
                          </span>
                          <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-500 group-hover:translate-x-0.5 transition-all duration-200" />
                        </div>
                      </Link>
                    </motion.div>
                  ))}
                </motion.div>
              </motion.div>
            )}

            {/* ── Footer ───────────────────────────────────────────────── */}
            <motion.p variants={itemVariants} className="text-xs text-slate-400 text-center pt-2 pb-4">
              UpMyRank · Physics · Chemistry · Maths · NCERT Class 11 &amp; 12 · GPT-4.1-mini
            </motion.p>

          </motion.div>
        </div>
      </main>
    </div>
    </AuthGuard>
  )
}
