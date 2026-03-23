'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { MessageCircle, Target, Timer, BarChart3, ChevronRight } from 'lucide-react'
import Sidebar from '@/components/Sidebar'
import { apiGet } from '@/lib/api'
import { TEST_STUDENT_ID } from '@/lib/constants'
import { StudentGenome } from '@/lib/types'

function masteryColor(m: number): string {
  if (m < 0.3) return '#EF4444'
  if (m < 0.7) return '#F59E0B'
  return '#22C55E'
}

interface MentorMeta {
  mode: string
  icon: string
  greeting: string
  accentColor: string
}

function getMentorMode(genome: StudentGenome): MentorMeta {
  const pct = Math.round(genome.overall_mastery * 100)
  const sessions = genome.total_sessions
  const w0 = genome.weakest_concepts[0]?.subtopic ?? '—'
  const w1 = genome.weakest_concepts[1]?.subtopic ?? '—'

  if (pct < 25) {
    return {
      mode: 'COUNSELOR', icon: '🧘', accentColor: '#9333EA',
      greeting: `Hey, no pressure today. You're at ${pct}% — let's take it one concept at a time and build the foundation properly. We'll start with ${w0}.`,
    }
  }
  if (sessions === 0) {
    return {
      mode: 'COACH', icon: '🏋️', accentColor: '#22C55E',
      greeting: `Welcome! Your Physics genome is ready. Your current mastery is ${pct}%. Let's start with your weakest area: ${w0}.`,
    }
  }
  if (pct > 60 && sessions > 5) {
    return {
      mode: 'STRATEGIST', icon: '🎯', accentColor: '#3B82F6',
      greeting: `You're at ${pct}% with ${sessions} sessions done — solid progress. Let's be strategic and close the gaps: focus on ${w0} and ${w1} today.`,
    }
  }
  return {
    mode: 'COACH', icon: '🏋️', accentColor: '#22C55E',
    greeting: `Good to see you! You're at ${pct}% overall. Today's focus: ${w0} and ${w1}. Let's improve those together.`,
  }
}

const ACTION_CARDS = [
  { icon: MessageCircle, title: 'Ask a doubt',  desc: "Type or upload a problem you're stuck on", href: '/doubt' },
  { icon: Target,        title: 'Practice now', desc: '5 problems picked for your weak areas',    href: '/practice' },
  { icon: Timer,         title: 'Mock test',    desc: 'Timed test · 10 questions · Exam conditions', href: '/mock' },
  { icon: BarChart3,     title: 'My progress',  desc: 'Knowledge genome · Study plan · Analytics', href: '/progress' },
]

export default function Home() {
  const [genome, setGenome] = useState<StudentGenome | null>(null)

  useEffect(() => {
    apiGet(`/student/${TEST_STUDENT_ID}`).then(setGenome).catch(console.error)
  }, [])

  const weakest = genome?.weakest_concepts ?? []
  const studyPlan = weakest.slice(0, 3).map((c) => ({
    subtopic: c.subtopic,
    mastery: c.mastery,
    problems: 5,
    time: '15–20 min',
  }))
  const mentor = genome ? getMentorMode(genome) : null

  return (
    <div className="flex h-full">
      <Sidebar />
      <main className="md:ml-[80px] flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-6 pb-24 md:pb-8 space-y-6">

          {/* Mentor greeting card */}
          <div
            className="rounded-2xl bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border-l-4 overflow-hidden"
            style={{ borderLeftColor: mentor?.accentColor ?? '#7C3AED' }}
          >
            <div className="px-6 py-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{mentor?.icon ?? '🎓'}</span>
                <span className="text-sm font-semibold" style={{ color: mentor?.accentColor ?? '#7C3AED' }}>
                  AI Mentor · {mentor?.mode ?? 'Loading…'}
                </span>
              </div>
              {genome ? (
                <p className="text-slate-700 leading-relaxed text-sm">{mentor?.greeting}</p>
              ) : (
                <p className="text-slate-400 text-sm">Loading your progress…</p>
              )}
            </div>
          </div>

          {/* Action cards 2×2 */}
          <div className="grid grid-cols-2 gap-4">
            {ACTION_CARDS.map((card) => (
              <Link
                key={card.href}
                href={card.href}
                className="group bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5 hover:bg-white/95 hover:shadow-md transition-all duration-200"
              >
                <card.icon className="h-5 w-5 text-indigo-500 mb-3" />
                <div className="font-semibold text-slate-800 mb-1">{card.title}</div>
                <div className="text-sm text-slate-500">{card.desc}</div>
              </Link>
            ))}
          </div>

          {/* Today's study plan */}
          {studyPlan.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Today&apos;s study plan
              </h2>
              <div className="space-y-2">
                {studyPlan.map((item, i) => (
                  <Link
                    key={i}
                    href="/practice"
                    className="flex items-center gap-4 bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-xl px-4 py-3 hover:bg-white/95 hover:shadow-sm transition-all"
                  >
                    <div className="w-5 h-5 rounded-full border-2 border-slate-200 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-slate-800 font-medium truncate">{item.subtopic}</div>
                      <div className="text-xs text-slate-400">{item.problems} problems · {item.time}</div>
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-2">
                      <span className="text-sm font-semibold" style={{ color: masteryColor(item.mastery) }}>
                        {Math.round(item.mastery * 100)}%
                      </span>
                      <ChevronRight className="h-4 w-4 text-slate-300" />
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Subject Overview */}
          {genome && Object.keys(genome.topic_mastery).length > 0 && (
            <div>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                Subject Overview
              </h2>
              <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5 space-y-4">
                {Object.entries(genome.topic_mastery).slice(0, 6).map(([topic, data]) => {
                  const pct = Math.round(data.average * 100)
                  const barColor = pct >= 70 ? '#22C55E' : pct >= 40 ? '#F59E0B' : '#EF4444'
                  return (
                    <div key={topic}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm text-slate-700 truncate pr-4">{topic}</span>
                        <span className="text-xs font-semibold flex-shrink-0" style={{ color: barColor }}>
                          {pct}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%`, backgroundColor: barColor }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="text-xs text-slate-400 text-center pt-4">
            UpMyRank POC · Built with FastAPI + pgvector + GPT-4o-mini · NCERT Physics Class 11 &amp; 12
          </div>

        </div>
      </main>
    </div>
  )
}
