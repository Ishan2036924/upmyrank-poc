'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import {
  ArrowLeft, RefreshCw, TrendingUp, Target, BookOpen, AlertTriangle, Zap,
} from 'lucide-react'
import {
  ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'
import AppShell from '@/components/AppShell'
import { apiGet } from '@/lib/api'
import { StudentGenome, ConceptMastery } from '@/lib/types'
import AuthGuard from '@/components/AuthGuard'
import { useAuth } from '@/lib/auth'

// ── Stagger animation variants ────────────────────────────────────────────────

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1]

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.05 } },
}

const cardVariants = {
  hidden:  { opacity: 0, y: 28, scale: 0.97 },
  visible: { opacity: 1, y: 0,  scale: 1, transition: { duration: 0.55, ease: EASE } },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function masteryColor(m: number) {
  if (m === 0) return '#94a3b8'
  if (m < 0.3) return '#EF4444'
  if (m < 0.6) return '#F59E0B'
  return '#22C55E'
}
function masteryLabel(m: number) {
  if (m === 0) return 'Unattempted'
  if (m < 0.3) return 'Needs work'
  if (m < 0.6) return 'Developing'
  return 'Strong'
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionLabel({ icon, text, sub }: { icon: React.ReactNode; text: string; sub?: string }) {
  return (
    <div className="flex items-center gap-2.5 mb-5">
      <span className="text-indigo-400">{icon}</span>
      <h2 className="text-sm font-semibold text-slate-700">{text}</h2>
      {sub && <span className="text-xs text-slate-400 ml-1">{sub}</span>}
    </div>
  )
}

function PriorityRow({ c, rank }: { c: ConceptMastery; rank: number }) {
  const pct = Math.round(c.mastery * 100)
  return (
    <motion.div
      variants={cardVariants}
      className="bg-white/80 backdrop-blur-md border border-white/50 shadow-[0_4px_20px_rgb(0,0,0,0.04)] rounded-2xl px-5 py-4 flex items-center gap-4 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out"
    >
      <span className="text-sm font-bold text-slate-200 w-5 text-center tabular-nums">{rank}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-slate-800 truncate pr-4">{c.subtopic}</span>
          <span className="text-xs font-semibold flex-shrink-0 tabular-nums" style={{ color: masteryColor(c.mastery) }}>
            {masteryLabel(c.mastery)} · {pct}%
          </span>
        </div>
        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${pct}%`, backgroundColor: masteryColor(c.mastery) }}
          />
        </div>
      </div>
      <Link
        href="/practice"
        className="flex-shrink-0 text-xs font-semibold text-indigo-500 hover:text-indigo-700 transition-colors"
      >
        Practice →
      </Link>
    </motion.div>
  )
}

function TrajectoryTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-100 rounded-xl px-3.5 py-2.5 text-xs shadow-[0_8px_30px_rgb(0,0,0,0.08)]">
      <div className="text-slate-500 mb-0.5">{label}</div>
      <div className="text-slate-900 font-bold">{payload[0].value}% mastery</div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const { studentId } = useAuth()
  const [genome, setGenome] = useState<StudentGenome | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      setGenome(await apiGet(`/student/${studentId}`))
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const overallPct   = genome ? Math.round(genome.overall_mastery * 100) : 0
  const resolvedPct  = genome && genome.total_sessions > 0
    ? Math.round((genome.resolved_sessions / genome.total_sessions) * 100) : 0
  const allConcepts: ConceptMastery[] = genome
    ? Object.values(genome.topic_mastery).flatMap((t) => t.concepts) : []
  const masteredCount    = allConcepts.filter((c) => c.mastery >= 0.7).length
  const inProgressCount  = allConcepts.filter((c) => c.mastery > 0 && c.mastery < 0.7).length
  const unattemptedCount = allConcepts.filter((c) => c.mastery === 0).length

  const trajectoryData = useMemo(() => {
    if (!genome) return []
    const target = genome.overall_mastery * 100
    return Array.from({ length: 30 }, (_, i) => {
      const t = i / 29
      const base = target * (0.55 + 0.45 * Math.sqrt(t))
      const noise = ((i * 7 + 13) % 11) - 5
      return {
        day: i === 0 ? 'Day 1' : i === 14 ? 'Day 15' : i === 29 ? 'Today' : `D${i + 1}`,
        mastery: Math.max(0, Math.min(100, Math.round(base + noise))),
        isLabel: i === 0 || i === 14 || i === 29,
      }
    })
  }, [genome])

  const radarData = useMemo(() => {
    if (!genome) return []
    return Object.entries(genome.topic_mastery)
      .slice(0, 8)
      .map(([topic, data]) => ({
        subject: topic.length > 14 ? topic.slice(0, 13) + '…' : topic,
        mastery: Math.round(data.average * 100),
        fullMark: 100,
      }))
  }, [genome])

  const activeConcepts = useMemo(() => {
    return allConcepts
      .filter((c) => c.mastery > 0)
      .sort((a, b) => b.mastery - a.mastery)
      .slice(0, 8)
  }, [allConcepts])

  const priorityTopics = genome?.weakest_concepts.slice(0, 6) ?? []

  const masteryAccentColor = overallPct >= 70 ? '#22C55E' : overallPct >= 40 ? '#F59E0B' : '#EF4444'
  const masteryAccentBg    = overallPct >= 70 ? 'rgba(34,197,94,0.12)' : overallPct >= 40 ? 'rgba(245,158,11,0.12)' : 'rgba(239,68,68,0.12)'

  return (
    <AuthGuard>
    <AppShell maxWidth="max-w-5xl">
        <div className="space-y-10">

          {/* ── Header ─────────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors">
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <div>
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">Analytics</h1>
                <p className="text-xs text-slate-400 mt-0.5 font-medium uppercase tracking-wide">NCERT Physics · Class 11 &amp; 12</p>
              </div>
            </div>
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 hover:bg-white px-3.5 py-2 text-sm text-slate-500 font-medium transition-all duration-300 ease-out hover:-translate-y-0.5 hover:shadow-sm disabled:opacity-40 shadow-sm active:scale-95"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {/* ── Loading / error ─────────────────────────────────────────────── */}
          {loading ? (
            <div className="grid grid-cols-3 gap-4">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className={`bg-white/60 rounded-3xl animate-pulse ${i === 0 ? 'col-span-2 h-52' : 'h-24'}`}
                />
              ))}
            </div>
          ) : !genome ? (
            <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-8 text-sm text-slate-400 text-center">
              Failed to load data. Try refreshing.
            </div>
          ) : (

            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="space-y-10"
            >

              {/* ── TIER 1: Bento stat cards ────────────────────────────── */}
              {/* 3-col grid: mastery spans 2 cols, right column stacks 2 cards */}
              <div className="grid grid-cols-3 gap-4 items-stretch">

                {/* Overall Mastery — wide hero card */}
                <motion.div
                  variants={cardVariants}
                  className="col-span-2 relative bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-1 hover:shadow-[0_16px_48px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out overflow-hidden"
                >
                  {/* Decorative orb */}
                  <div
                    className="absolute top-0 right-0 w-48 h-48 rounded-full -translate-y-16 translate-x-16 pointer-events-none"
                    style={{ background: `radial-gradient(circle, ${masteryAccentBg} 0%, transparent 70%)` }}
                  />
                  <div className="relative">
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-5 flex items-center gap-2">
                      <TrendingUp className="h-3.5 w-3.5" />
                      Overall Mastery
                    </p>
                    <p
                      className="text-6xl font-extrabold tracking-tight leading-none mb-4"
                      style={{ color: masteryAccentColor }}
                    >
                      {overallPct}<span className="text-3xl font-bold text-slate-300 ml-1">%</span>
                    </p>
                    <p className="text-sm text-slate-500">
                      {genome.overall_mastery === 0
                        ? 'Ask your first doubt to start building your genome.'
                        : `${masteryLabel(genome.overall_mastery)} — you're making real progress 💪`}
                    </p>
                    {/* Mini concept progress bar */}
                    <div className="mt-6 grid grid-cols-3 gap-4">
                      {[
                        { label: 'Mastered',    count: masteredCount,    color: '#22C55E' },
                        { label: 'In Progress', count: inProgressCount,  color: '#F59E0B' },
                        { label: 'Unattempted', count: unattemptedCount, color: '#94a3b8' },
                      ].map((s) => (
                        <div key={s.label}>
                          <p className="text-2xl font-bold text-slate-900 tabular-nums">{s.count}</p>
                          <p className="text-xs text-slate-400 mt-0.5">{s.label}</p>
                          <div className="mt-1.5 h-1 rounded-full" style={{ backgroundColor: s.color, opacity: 0.6 }} />
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>

                {/* Right column: two stacked cards */}
                <div className="flex flex-col gap-4">

                  {/* Session Accuracy */}
                  <motion.div
                    variants={cardVariants}
                    className="flex-1 relative bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-1 hover:shadow-[0_16px_48px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out overflow-hidden"
                  >
                    <div className="absolute top-0 right-0 w-24 h-24 rounded-full -translate-y-8 translate-x-8 pointer-events-none"
                      style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.10) 0%, transparent 70%)' }} />
                    <div className="relative">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                        <Target className="h-3 w-3" /> Session Accuracy
                      </p>
                      <p className="text-4xl font-extrabold text-blue-500 tracking-tight">{resolvedPct}<span className="text-xl font-bold text-slate-300 ml-0.5">%</span></p>
                      <p className="text-xs text-slate-400 mt-2">{genome.resolved_sessions} resolved of {genome.total_sessions} sessions</p>
                    </div>
                  </motion.div>

                  {/* Concepts Mastered */}
                  <motion.div
                    variants={cardVariants}
                    className="flex-1 relative bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-1 hover:shadow-[0_16px_48px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out overflow-hidden"
                  >
                    <div className="absolute top-0 right-0 w-24 h-24 rounded-full -translate-y-8 translate-x-8 pointer-events-none"
                      style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.10) 0%, transparent 70%)' }} />
                    <div className="relative">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                        <BookOpen className="h-3 w-3" /> Concepts Mastered
                      </p>
                      <p className="text-4xl font-extrabold text-indigo-500 tracking-tight tabular-nums">{masteredCount}<span className="text-base font-semibold text-slate-300 ml-1">/{allConcepts.length}</span></p>
                      <p className="text-xs text-slate-400 mt-2">{inProgressCount} in progress · {unattemptedCount} unattempted</p>
                    </div>
                  </motion.div>

                </div>
              </div>

              {/* ── TIER 2: Charts bento ────────────────────────────────── */}
              <div className="grid grid-cols-3 gap-4">

                {/* Mastery Trajectory — wide */}
                <motion.div
                  variants={cardVariants}
                  className="col-span-2 bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-1 hover:shadow-[0_16px_48px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out"
                >
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1">Mastery Trajectory</p>
                  <p className="text-slate-400 text-xs mb-5">Simulated 30-day learning curve</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={trajectoryData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="day" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
                      <Tooltip content={<TrajectoryTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="mastery"
                        stroke="#6366f1"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 5, fill: '#6366f1', strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </motion.div>

                {/* Topic Radar */}
                <motion.div
                  variants={cardVariants}
                  className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-1 hover:shadow-[0_16px_48px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out"
                >
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1">Topic Breakdown</p>
                  <p className="text-slate-400 text-xs mb-3">Mastery per chapter</p>
                  <ResponsiveContainer width="100%" height={200}>
                    <RadarChart data={radarData} margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                      <PolarGrid stroke="#e2e8f0" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#cbd5e1', fontSize: 9 }} tickCount={3} tickFormatter={(v) => `${v}%`} />
                      <Radar name="Mastery" dataKey="mastery" stroke="#6366f1" fill="#6366f1" fillOpacity={0.15} strokeWidth={2} />
                      <Tooltip
                        contentStyle={{
                          background: '#fff', border: '1px solid #e2e8f0',
                          borderRadius: 12, fontSize: 12, color: '#1e293b',
                          boxShadow: '0 8px 30px rgba(0,0,0,0.08)',
                        }}
                        formatter={(v) => [`${v ?? 0}%`, 'Mastery']}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </motion.div>

              </div>

              {/* ── Active Concepts ─────────────────────────────────────── */}
              {activeConcepts.length > 0 && (
                <div>
                  <SectionLabel icon={<Zap className="h-4 w-4" />} text="Active Concepts" sub="— concepts you've started working on" />
                  <motion.div variants={containerVariants} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {activeConcepts.map((c) => {
                      const pct = Math.round(c.mastery * 100)
                      return (
                        <motion.div
                          key={c.concept_id}
                          variants={cardVariants}
                          className="bg-white/80 backdrop-blur-md border border-white/50 rounded-2xl px-5 py-4 flex flex-col gap-2.5 shadow-[0_4px_20px_rgb(0,0,0,0.04)] hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-semibold text-slate-800 truncate">{c.subtopic}</span>
                            <span className="text-sm font-bold tabular-nums flex-shrink-0" style={{ color: masteryColor(c.mastery) }}>{pct}%</span>
                          </div>
                          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-700"
                              style={{ width: `${pct}%`, backgroundColor: masteryColor(c.mastery) }}
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium" style={{ color: masteryColor(c.mastery) }}>{masteryLabel(c.mastery)}</span>
                            {c.error_count > 0 && (
                              <span className="text-xs text-slate-400">{c.error_count} error{c.error_count !== 1 ? 's' : ''}</span>
                            )}
                          </div>
                        </motion.div>
                      )
                    })}
                  </motion.div>
                </div>
              )}

              {/* ── Priority Topics ─────────────────────────────────────── */}
              <div>
                <SectionLabel icon={<AlertTriangle className="h-4 w-4 text-amber-400" />} text="Priority Topics" sub="— weakest concepts, focus here first" />
                {priorityTopics.length === 0 ? (
                  <motion.div variants={cardVariants} className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl px-6 py-8 text-sm text-slate-400 text-center">
                    No concept data yet — ask some doubts to build your profile!
                  </motion.div>
                ) : (
                  <motion.div variants={containerVariants} className="space-y-3">
                    {priorityTopics.map((c, i) => (
                      <PriorityRow key={c.concept_id} c={c} rank={i + 1} />
                    ))}
                  </motion.div>
                )}
              </div>

            </motion.div>
          )}
        </div>
    </AppShell>
    </AuthGuard>
  )
}
