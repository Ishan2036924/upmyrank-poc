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

function masteryColor(m: number) {
  if (m === 0) return '#94a3b8'   // slate-400 — unattempted
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

function StatCard({
  icon, label, value, sub, accent,
}: {
  icon: React.ReactNode; label: string; value: string; sub: string; accent: string
}) {
  return (
    <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</span>
        <span className="text-slate-300">{icon}</span>
      </div>
      <div className={`text-4xl font-bold ${accent}`}>{value}</div>
      <div className="text-xs text-slate-500">{sub}</div>
    </div>
  )
}

function PriorityRow({ c, rank }: { c: ConceptMastery; rank: number }) {
  const pct = Math.round(c.mastery * 100)
  return (
    <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-xl px-5 py-4 flex items-center gap-4">
      <span className="text-sm font-bold text-slate-300 w-5 text-center">{rank}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-slate-800 truncate pr-4">{c.subtopic}</span>
          <span className="text-xs font-semibold flex-shrink-0" style={{ color: masteryColor(c.mastery) }}>
            {masteryLabel(c.mastery)} · {pct}%
          </span>
        </div>
        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
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
    </div>
  )
}

function TrajectoryTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs shadow-lg">
      <div className="text-slate-500">{label}</div>
      <div className="text-slate-800 font-semibold">{payload[0].value}% mastery</div>
    </div>
  )
}

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

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="md:ml-[80px] flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8 pb-24 md:pb-10 space-y-8">

          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors">
                <ArrowLeft className="h-5 w-5" />
              </Link>
              <div>
                <h1 className="text-xl font-bold text-slate-800">Analytics</h1>
                <p className="text-xs text-slate-400 mt-0.5">NCERT Physics · Class 11 &amp; 12</p>
              </div>
            </div>
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 hover:bg-white px-3 py-2 text-sm text-slate-500 font-medium transition-colors disabled:opacity-40 shadow-sm"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="text-slate-400 text-sm">Loading your analytics…</div>
          ) : !genome ? (
            <div className="text-slate-400 text-sm">Failed to load data. Try refreshing.</div>
          ) : (
            <>
              {/* TIER 1: Stat cards */}
              <div className="grid grid-cols-3 gap-4">
                <StatCard
                  icon={<TrendingUp className="h-4 w-4" />}
                  label="Overall Mastery"
                  value={`${overallPct}%`}
                  sub={genome.overall_mastery === 0 ? 'Ask a doubt to get started!' : `${masteryLabel(genome.overall_mastery)} — keep going 💪`}
                  accent={overallPct >= 70 ? 'text-emerald-500' : overallPct >= 40 ? 'text-amber-500' : 'text-red-500'}
                />
                <StatCard
                  icon={<Target className="h-4 w-4" />}
                  label="Session Accuracy"
                  value={`${resolvedPct}%`}
                  sub={`${genome.resolved_sessions} resolved of ${genome.total_sessions} sessions`}
                  accent="text-blue-500"
                />
                <StatCard
                  icon={<BookOpen className="h-4 w-4" />}
                  label="Concepts Mastered"
                  value={`${masteredCount}/${allConcepts.length}`}
                  sub={`${inProgressCount} in progress · ${unattemptedCount} unattempted`}
                  accent="text-indigo-500"
                />
              </div>

              {/* TIER 2: Charts */}
              <div className="grid grid-cols-2 gap-6">

                {/* Mastery trajectory */}
                <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5">
                  <div className="mb-4">
                    <h2 className="text-sm font-semibold text-slate-700">Mastery Trajectory</h2>
                    <p className="text-xs text-slate-400 mt-0.5">Simulated 30-day learning curve</p>
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={trajectoryData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis
                        dataKey="day"
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
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
                <div className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-2xl p-5">
                  <div className="mb-4">
                    <h2 className="text-sm font-semibold text-slate-700">Topic Skill Breakdown</h2>
                    <p className="text-xs text-slate-400 mt-0.5">Radar of mastery per chapter</p>
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <RadarChart data={radarData} margin={{ top: 0, right: 20, bottom: 0, left: 20 }}>
                      <PolarGrid stroke="#e2e8f0" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                      <PolarRadiusAxis
                        angle={30}
                        domain={[0, 100]}
                        tick={{ fill: '#cbd5e1', fontSize: 9 }}
                        tickCount={3}
                        tickFormatter={(v) => `${v}%`}
                      />
                      <Radar
                        name="Mastery"
                        dataKey="mastery"
                        stroke="#6366f1"
                        fill="#6366f1"
                        fillOpacity={0.15}
                        strokeWidth={2}
                      />
                      <Tooltip
                        contentStyle={{
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: 12,
                          fontSize: 12,
                          color: '#1e293b',
                          boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
                        }}
                        formatter={(v) => [`${v ?? 0}%`, 'Mastery']}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Active Concepts */}
              {activeConcepts.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Zap className="h-4 w-4 text-indigo-500" />
                    <h2 className="text-sm font-semibold text-slate-700">Active Concepts</h2>
                    <span className="text-xs text-slate-400 ml-1">— concepts you&apos;ve started working on</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {activeConcepts.map((c) => {
                      const pct = Math.round(c.mastery * 100)
                      return (
                        <div
                          key={c.concept_id}
                          className="bg-white/80 backdrop-blur-md border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-xl px-4 py-3 flex flex-col gap-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-semibold text-slate-800 truncate">{c.subtopic}</span>
                            <span className="text-xs font-semibold flex-shrink-0 tabular-nums" style={{ color: masteryColor(c.mastery) }}>
                              {pct}%
                            </span>
                          </div>
                          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{ width: `${pct}%`, backgroundColor: masteryColor(c.mastery) }}
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium" style={{ color: masteryColor(c.mastery) }}>
                              {masteryLabel(c.mastery)}
                            </span>
                            {c.error_count > 0 && (
                              <span className="text-xs text-slate-400">
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

              {/* TIER 3: Priority topics */}
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                  <h2 className="text-sm font-semibold text-slate-700">Priority Topics</h2>
                  <span className="text-xs text-slate-400 ml-1">— weakest concepts, focus here first</span>
                </div>

                {priorityTopics.length === 0 ? (
                  <div className="bg-white/80 backdrop-blur-md border border-white/60 rounded-xl px-5 py-6 text-sm text-slate-400 text-center">
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
