'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import {
  ArrowLeft, RefreshCw, ShieldCheck, Zap, Database,
  AlertTriangle, CheckCircle2, TrendingUp, Clock,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from 'recharts'
import { apiGet } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface TopicMetric {
  topic: string
  avg_score: number
  session_count: number
  avg_retrieval_similarity: number | null
  avg_latency_ms: number | null
  is_drifting: boolean
}

interface AdminMetrics {
  period_days: number
  total_scored: number
  socratic_adherence_rate: number
  avg_retrieval_similarity: number | null
  latency_p95_ms: number | null
  topics: TopicMetric[]
}

// ── Animation variants ────────────────────────────────────────────────────────

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1]

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
}

const cardVariants = {
  hidden:  { opacity: 0, y: 24, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.5, ease: EASE } },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 1.7) return '#22C55E'
  if (score >= 1.2) return '#F59E0B'
  return '#EF4444'
}

function scoreLabel(score: number): string {
  if (score >= 1.7) return 'Excellent'
  if (score >= 1.2) return 'Acceptable'
  return 'Drifting'
}

function adherenceColor(rate: number): string {
  if (rate >= 0.8) return '#22C55E'
  if (rate >= 0.6) return '#F59E0B'
  return '#EF4444'
}

// ── Custom tooltip ────────────────────────────────────────────────────────────

function ScoreTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  const score = payload[0].value
  return (
    <div className="bg-white border border-slate-100 rounded-xl px-3.5 py-2.5 text-xs shadow-[0_8px_30px_rgb(0,0,0,0.08)]">
      <div className="text-slate-500 mb-0.5 max-w-[160px] truncate">{label}</div>
      <div className="font-bold" style={{ color: scoreColor(score) }}>
        {scoreLabel(score)} · {score.toFixed(2)}
      </div>
    </div>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label, value, unit, sub, accentColor, accentBg, icon,
}: {
  label: string; value: string; unit?: string; sub?: string
  accentColor: string; accentBg: string; icon: React.ReactNode
}) {
  return (
    <motion.div
      variants={cardVariants}
      className="relative bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-7 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-1 hover:shadow-[0_16px_48px_rgb(0,0,0,0.08)] transition-all duration-300 ease-out overflow-hidden"
    >
      <div
        className="absolute top-0 right-0 w-40 h-40 rounded-full -translate-y-12 translate-x-12 pointer-events-none"
        style={{ background: `radial-gradient(circle, ${accentBg} 0%, transparent 70%)` }}
      />
      <div className="relative">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-2">
          <span style={{ color: accentColor }}>{icon}</span>
          {label}
        </p>
        <p className="text-5xl font-extrabold tracking-tight leading-none mb-2" style={{ color: accentColor }}>
          {value}
          {unit && <span className="text-2xl font-bold text-slate-300 ml-1">{unit}</span>}
        </p>
        {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      </div>
    </motion.div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const [metrics, setMetrics]   = useState<AdminMetrics | null>(null)
  const [loading, setLoading]   = useState(true)
  const [days, setDays]         = useState(7)

  const fetchMetrics = async (d = days) => {
    setLoading(true)
    try {
      setMetrics(await apiGet(`/admin/metrics?days=${d}`))
    } catch (e) {
      console.error('Admin metrics fetch failed', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchMetrics(days) }, [days])

  const adherencePct = metrics ? Math.round(metrics.socratic_adherence_rate * 100) : 0
  const driftingCount = metrics?.topics.filter((t) => t.is_drifting).length ?? 0

  // Bar chart data: topics sorted by avg_score desc for readability
  const chartData = metrics
    ? [...metrics.topics]
        .sort((a, b) => b.avg_score - a.avg_score)
        .map((t) => ({
          name: t.topic.length > 22 ? t.topic.slice(0, 21) + '…' : t.topic,
          score: t.avg_score,
        }))
    : []

  return (
    <div className="min-h-screen">
      <div className="max-w-5xl mx-auto px-6 py-8 pb-16 space-y-10">

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">Eval Dashboard</h1>
              <p className="text-xs text-slate-400 mt-0.5 font-medium uppercase tracking-wide">
                Pedagogy quality · Judge LLM metrics
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Period selector */}
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                  days === d
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'bg-white/80 border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-white'
                }`}
              >
                {d}d
              </button>
            ))}
            <button
              onClick={() => fetchMetrics(days)}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 hover:bg-white px-3.5 py-2 text-sm text-slate-500 font-medium transition-all duration-300 hover:-translate-y-0.5 hover:shadow-sm disabled:opacity-40 shadow-sm active:scale-95 ml-2"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* ── No data state ───────────────────────────────────────────────────── */}
        {!loading && metrics && metrics.total_scored === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-10 text-center shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
          >
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-slate-50 border border-slate-100 mb-4">
              <Database className="h-6 w-6 text-slate-300" />
            </div>
            <p className="text-sm font-semibold text-slate-700 mb-1">No scored sessions yet</p>
            <p className="text-xs text-slate-400 max-w-xs mx-auto">
              Eval data will appear here after students use the tutor and the Judge LLM has scored responses.
            </p>
          </motion.div>
        )}

        {/* ── Loading skeleton ────────────────────────────────────────────────── */}
        {loading && (
          <div className="space-y-6">
            <div className="grid grid-cols-3 gap-4">
              {[0, 1, 2].map((i) => (
                <div key={i} className="bg-white/60 rounded-3xl animate-pulse h-36" />
              ))}
            </div>
            <div className="bg-white/60 rounded-3xl animate-pulse h-64" />
          </div>
        )}

        {/* ── Dashboard ───────────────────────────────────────────────────────── */}
        {!loading && metrics && metrics.total_scored > 0 && (
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-8"
          >
            {/* ── Status banner ─────────────────────────────────────────── */}
            {driftingCount > 0 ? (
              <motion.div
                variants={cardVariants}
                className="flex items-center gap-3 rounded-2xl bg-red-50/80 border border-red-200 px-5 py-3.5 text-sm text-red-700 font-medium backdrop-blur-sm"
              >
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                <span>
                  <strong>{driftingCount} topic{driftingCount !== 1 ? 's' : ''}</strong> below the pedagogy drift threshold (avg score &lt; 1.5) — review Socratic prompt quality.
                </span>
              </motion.div>
            ) : (
              <motion.div
                variants={cardVariants}
                className="flex items-center gap-3 rounded-2xl bg-emerald-50/80 border border-emerald-200 px-5 py-3.5 text-sm text-emerald-700 font-medium backdrop-blur-sm"
              >
                <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                <span>All topics within acceptable Socratic quality range.</span>
              </motion.div>
            )}

            {/* ── Hero stat cards ────────────────────────────────────────── */}
            <div className="grid grid-cols-3 gap-4">
              <StatCard
                label="Socratic Adherence"
                value={`${adherencePct}`}
                unit="%"
                sub={`${metrics.total_scored} scored responses · last ${metrics.period_days}d`}
                accentColor={adherenceColor(metrics.socratic_adherence_rate)}
                accentBg={
                  adherencePct >= 80 ? 'rgba(34,197,94,0.12)'
                  : adherencePct >= 60 ? 'rgba(245,158,11,0.12)'
                  : 'rgba(239,68,68,0.12)'
                }
                icon={<ShieldCheck className="h-3.5 w-3.5" />}
              />
              <StatCard
                label="Retrieval Confidence"
                value={
                  metrics.avg_retrieval_similarity != null
                    ? (metrics.avg_retrieval_similarity * 100).toFixed(1)
                    : '—'
                }
                unit={metrics.avg_retrieval_similarity != null ? '%' : undefined}
                sub="Avg cosine similarity (RAG)"
                accentColor="#6366f1"
                accentBg="rgba(99,102,241,0.10)"
                icon={<Database className="h-3.5 w-3.5" />}
              />
              <StatCard
                label="Latency P95"
                value={metrics.latency_p95_ms != null ? `${metrics.latency_p95_ms}` : '—'}
                unit={metrics.latency_p95_ms != null ? 'ms' : undefined}
                sub="95th-percentile LLM response time"
                accentColor="#0ea5e9"
                accentBg="rgba(14,165,233,0.10)"
                icon={<Clock className="h-3.5 w-3.5" />}
              />
            </div>

            {/* ── Per-topic score bar chart ──────────────────────────────── */}
            {chartData.length > 0 && (
              <motion.div
                variants={cardVariants}
                className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-0.5 hover:shadow-[0_16px_48px_rgb(0,0,0,0.07)] transition-all duration-300"
              >
                <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1 flex items-center gap-2">
                  <TrendingUp className="h-3.5 w-3.5 text-indigo-400" />
                  Avg Socratic Score by Topic
                </p>
                <p className="text-xs text-slate-400 mb-6">0 = gave answer · 1 = vague hint · 2 = Socratic question. Threshold: 1.5</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 40, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      angle={-30}
                      textAnchor="end"
                      interval={0}
                    />
                    <YAxis
                      domain={[0, 2]}
                      ticks={[0, 0.5, 1.0, 1.5, 2.0]}
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    {/* Drift threshold reference at 1.5 — drawn via background fill trick */}
                    <Tooltip content={<ScoreTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
                    <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={scoreColor(entry.score)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                {/* Legend */}
                <div className="flex items-center gap-5 mt-2 justify-center">
                  {[
                    { color: '#22C55E', label: 'Excellent (≥1.7)' },
                    { color: '#F59E0B', label: 'Acceptable (1.2–1.7)' },
                    { color: '#EF4444', label: 'Drifting (<1.2)' },
                  ].map((l) => (
                    <div key={l.label} className="flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: l.color }} />
                      <span className="text-[11px] text-slate-400">{l.label}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* ── Per-topic table ────────────────────────────────────────── */}
            {metrics.topics.length > 0 && (
              <motion.div
                variants={cardVariants}
                className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
              >
                <div className="px-6 py-5 border-b border-slate-100">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-2">
                    <Zap className="h-3.5 w-3.5 text-indigo-400" />
                    Topic Breakdown
                  </p>
                </div>
                <div className="divide-y divide-slate-100/80">
                  {metrics.topics.map((t) => (
                    <div
                      key={t.topic}
                      className="px-6 py-4 flex items-center gap-4 hover:bg-slate-50/60 transition-colors"
                    >
                      {/* Drift indicator */}
                      <div className="flex-shrink-0">
                        {t.is_drifting ? (
                          <AlertTriangle className="h-4 w-4 text-red-400" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        )}
                      </div>

                      {/* Topic name */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-slate-800 truncate">{t.topic}</p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {t.session_count} session{t.session_count !== 1 ? 's' : ''}
                          {t.avg_retrieval_similarity != null && (
                            <> · {(t.avg_retrieval_similarity * 100).toFixed(1)}% retrieval</>
                          )}
                          {t.avg_latency_ms != null && (
                            <> · {t.avg_latency_ms}ms avg latency</>
                          )}
                        </p>
                      </div>

                      {/* Score bar */}
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                              width: `${(t.avg_score / 2) * 100}%`,
                              backgroundColor: scoreColor(t.avg_score),
                            }}
                          />
                        </div>
                        <span
                          className="text-sm font-bold tabular-nums w-10 text-right"
                          style={{ color: scoreColor(t.avg_score) }}
                        >
                          {t.avg_score.toFixed(2)}
                        </span>
                        <span
                          className="text-xs font-medium px-2 py-0.5 rounded-full"
                          style={{
                            color: scoreColor(t.avg_score),
                            backgroundColor: `${scoreColor(t.avg_score)}18`,
                          }}
                        >
                          {scoreLabel(t.avg_score)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

          </motion.div>
        )}
      </div>
    </div>
  )
}
