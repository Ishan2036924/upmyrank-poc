'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft, RefreshCw, TrendingUp, Target, BookOpen, AlertTriangle, Zap,
} from 'lucide-react'
import {
  ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'
import Sidebar from '@/components/Sidebar'
import { apiGet } from '@/lib/api'
import { TEST_STUDENT_ID } from '@/lib/constants'
import { StudentGenome, ConceptMastery } from '@/lib/types'

// ── Colour helpers ──────────────────────────────────────────────────────────
function masteryColor(m: number) {
  if (m === 0) return '#52525b'   // zinc-600 — unattempted
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

// ── Tier 1: Stat card ───────────────────────────────────────────────────────
function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode
  label: string
  value: string
  sub: string
  accent: string   // Tailwind colour class for the value
}) {
  return (
    <div className="bg-zinc-900 border border-white/5 rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">{label}</span>
        <span className="text-zinc-700">{icon}</span>
      </div>
      <div className={`text-4xl font-bold ${accent}`}>{value}</div>
      <div className="text-xs text-zinc-500">{sub}</div>
    </div>
  )
}

// ── Tier 3: Priority topic row ──────────────────────────────────────────────
function PriorityRow({ c, rank }: { c: ConceptMastery; rank: number }) {
  const pct = Math.round(c.mastery * 100)
  return (
    <div className="bg-zinc-900 border border-white/5 rounded-xl px-5 py-4 flex items-center gap-4">
      <span className="text-sm font-bold text-zinc-600 w-5 text-center">{rank}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-zinc-100 truncate pr-4">{c.subtopic}</span>
          <span className="text-xs font-semibold flex-shrink-0" style={{ color: masteryColor(c.mastery) }}>
            {masteryLabel(c.mastery)} · {pct}%
          </span>
        </div>
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%`, backgroundColor: masteryColor(c.mastery) }}
          />
        </div>
      </div>
      <Link
        href="/practice"
        className="flex-shrink-0 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
      >
        Practice →
      </Link>
    </div>
  )
}

// ── Custom tooltip for LineChart ────────────────────────────────────────────
function TrajectoryTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-zinc-800 border border-white/10 rounded-lg px-3 py-2 text-xs">
      <div className="text-zinc-400">{label}</div>
      <div className="text-white font-semibold">{payload[0].value}% mastery</div>
    </div>
  )
}

// ── Main page ───────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [genome, setGenome] = useState<StudentGenome | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      setGenome(await apiGet(`/student/${TEST_STUDENT_ID}`))
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  // ── Derived stats ─────────────────────────────────────────────────────────
  const overallPct   = genome ? Math.round(genome.overall_mastery * 100) : 0
  const resolvedPct  = genome && genome.total_sessions > 0
    ? Math.round((genome.resolved_sessions / genome.total_sessions) * 100)
    : 0
  const allConcepts: ConceptMastery[] = genome
    ? Object.values(genome.topic_mastery).flatMap((t) => t.concepts)
    : []
  const masteredCount   = allConcepts.filter((c) => c.mastery >= 0.7).length
  const inProgressCount = allConcepts.filter((c) => c.mastery > 0 && c.mastery < 0.7).length
  const unattemptedCount = allConcepts.filter((c) => c.mastery === 0).length

  // ── Trajectory data (seeded 30-day simulation based on current mastery) ───
  const trajectoryData = useMemo(() => {
    if (!genome) return []
    const target = genome.overall_mastery * 100
    // Simulate a learning curve ending at current mastery
    return Array.from({ length: 30 }, (_, i) => {
      const t = i / 29
      // Logarithmic growth + small deterministic noise (avoids re-random on render)
      const base = target * (0.55 + 0.45 * Math.sqrt(t))
      const noise = ((i * 7 + 13) % 11) - 5   // deterministic ±5 jitter
      return {
        day: i === 0 ? 'Day 1' : i === 14 ? 'Day 15' : i === 29 ? 'Today' : `D${i + 1}`,
        mastery: Math.max(0, Math.min(100, Math.round(base + noise))),
        isLabel: i === 0 || i === 14 || i === 29,
      }
    })
  }, [genome])

  // ── Radar data from topic_mastery ─────────────────────────────────────────
  const radarData = useMemo(() => {
    if (!genome) return []
    return Object.entries(genome.topic_mastery)
      .slice(0, 8)   // cap at 8 spokes for readability
      .map(([topic, data]) => ({
        subject: topic.length > 14 ? topic.slice(0, 13) + '…' : topic,
        mastery: Math.round(data.average * 100),
        fullMark: 100,
      }))
  }, [genome])

  // ── Active concepts: attempted, sorted by mastery desc ───────────────────
  const activeConcepts = useMemo(() => {
    return allConcepts
      .filter((c) => c.mastery > 0)
      .sort((a, b) => b.mastery - a.mastery)
      .slice(0, 8)
  }, [allConcepts])

  // ── Weakest topics for Tier 3 (sorted weakest-first) ─────────────────────
  const priorityTopics = genome?.weakest_concepts.slice(0, 6) ?? []

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="md:ml-[280px] flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-8 py-8 pb-24 md:pb-10 space-y-10">

          {/* ── Header ─────────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/" className="text-zinc-500 hover:text-zinc-200 transition-colors">
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <div>
                <h1 className="text-xl font-bold text-zinc-50">Analytics</h1>
                <p className="text-xs text-zinc-500 mt-0.5">NCERT Physics · Class 11 &amp; 12</p>
              </div>
            </div>
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg border border-white/5 bg-zinc-900 hover:bg-zinc-800 px-3 py-2 text-sm text-zinc-400 transition-colors disabled:opacity-40"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="text-zinc-500 text-sm">Loading your analytics…</div>
          ) : !genome ? (
            <div className="text-zinc-500 text-sm">Failed to load data. Try refreshing.</div>
          ) : (
            <>
              {/* ── TIER 1: Summary stat cards ──────────────────────────────── */}
              <div className="grid grid-cols-3 gap-4">
                <StatCard
                  icon={<TrendingUp className="h-4 w-4" />}
                  label="Overall Mastery"
                  value={`${overallPct}%`}
                  sub={genome.overall_mastery === 0 ? 'Ask a doubt to get started!' : `${masteryLabel(genome.overall_mastery)} — keep going 💪`}
                  accent={
                    overallPct >= 70 ? 'text-green-400'
                    : overallPct >= 40 ? 'text-amber-400'
                    : 'text-red-400'
                  }
                />
                <StatCard
                  icon={<Target className="h-4 w-4" />}
                  label="Session Accuracy"
                  value={`${resolvedPct}%`}
                  sub={`${genome.resolved_sessions} resolved of ${genome.total_sessions} sessions`}
                  accent="text-blue-400"
                />
                <StatCard
                  icon={<BookOpen className="h-4 w-4" />}
                  label="Concepts Mastered"
                  value={`${masteredCount}/${allConcepts.length}`}
                  sub={`${inProgressCount} in progress · ${unattemptedCount} unattempted`}
                  accent="text-indigo-400"
                />
              </div>

              {/* ── TIER 2: Charts ──────────────────────────────────────────── */}
              <div className="grid grid-cols-2 gap-6">

                {/* Mastery trajectory */}
                <div className="bg-zinc-900 border border-white/5 rounded-2xl p-5">
                  <div className="mb-4">
                    <h2 className="text-sm font-semibold text-zinc-200">Mastery Trajectory</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">Simulated 30-day learning curve</p>
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={trajectoryData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                      <XAxis
                        dataKey="day"
                        tick={{ fill: '#71717a', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        interval={(i) => trajectoryData[i]?.isLabel}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: '#71717a', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => `${v}%`}
                      />
                      <Tooltip content={<TrajectoryTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="mastery"
                        stroke="#6366f1"
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 4, fill: '#6366f1', strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Topic radar */}
                <div className="bg-zinc-900 border border-white/5 rounded-2xl p-5">
                  <div className="mb-4">
                    <h2 className="text-sm font-semibold text-zinc-200">Topic Skill Breakdown</h2>
                    <p className="text-xs text-zinc-500 mt-0.5">Radar of mastery per chapter</p>
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <RadarChart data={radarData} margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                      <PolarGrid stroke="#27272a" />
                      <PolarAngleAxis
                        dataKey="subject"
                        tick={{ fill: '#71717a', fontSize: 9 }}
                      />
                      <PolarRadiusAxis
                        angle={30}
                        domain={[0, 100]}
                        tick={{ fill: '#52525b', fontSize: 9 }}
                        tickCount={3}
                        tickFormatter={(v) => `${v}%`}
                      />
                      <Radar
                        name="Mastery"
                        dataKey="mastery"
                        stroke="#6366f1"
                        fill="#6366f1"
                        fillOpacity={0.25}
                        strokeWidth={2}
                      />
                      <Tooltip
                        contentStyle={{
                          background: '#18181b',
                          border: '1px solid rgba(255,255,255,0.08)',
                          borderRadius: 8,
                          fontSize: 12,
                          color: '#fafafa',
                        }}
                        formatter={(v: number) => [`${v}%`, 'Mastery']}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* ── Active Concepts ─────────────────────────────────────────── */}
              {activeConcepts.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Zap className="h-4 w-4 text-indigo-400" />
                    <h2 className="text-sm font-semibold text-zinc-200">Active Concepts</h2>
                    <span className="text-xs text-zinc-600 ml-1">— concepts you&apos;ve started working on</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {activeConcepts.map((c) => {
                      const pct = Math.round(c.mastery * 100)
                      return (
                        <div
                          key={c.concept_id}
                          className="bg-zinc-900 border border-white/5 rounded-xl px-4 py-3 flex flex-col gap-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-medium text-zinc-100 truncate">{c.subtopic}</span>
                            <span
                              className="text-xs font-semibold flex-shrink-0 tabular-nums"
                              style={{ color: masteryColor(c.mastery) }}
                            >
                              {pct}%
                            </span>
                          </div>
                          <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{ width: `${pct}%`, backgroundColor: masteryColor(c.mastery) }}
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <span
                              className="text-xs"
                              style={{ color: masteryColor(c.mastery) }}
                            >
                              {masteryLabel(c.mastery)}
                            </span>
                            {c.error_count > 0 && (
                              <span className="text-xs text-zinc-600">
                                {c.error_count} error{c.error_count !== 1 ? 's' : ''}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* ── TIER 3: Priority topics ─────────────────────────────────── */}
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <h2 className="text-sm font-semibold text-zinc-200">Priority Topics</h2>
                  <span className="text-xs text-zinc-600 ml-1">— weakest concepts, focus here first</span>
                </div>

                {priorityTopics.length === 0 ? (
                  <div className="bg-zinc-900 border border-white/5 rounded-xl px-5 py-6 text-sm text-zinc-500 text-center">
                    No concept data yet — ask some doubts to build your profile!
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {priorityTopics.map((c, i) => (
                      <PriorityRow key={c.concept_id} c={c} rank={i + 1} />
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  )
}
