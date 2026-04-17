'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity, BarChart2, MessageSquare, Zap, ThumbsUp, BookOpen,
  Users, Stethoscope, ChevronDown, ChevronUp, RefreshCw, Loader2,
  CheckCircle2, AlertTriangle, XCircle, Sparkles, TrendingUp,
  TrendingDown, Minus, Globe, Clock, Database, Star,
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, AreaChart, Area, Legend, PieChart, Pie, Cell, RadialBarChart, RadialBar,
} from 'recharts'
import { apiGet, apiPost } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

type Section =
  | 'platform' | 'conv-quality' | 'response-quality'
  | 'system-perf' | 'feedback' | 'knowledge' | 'students' | 'diagnostics'

interface TurnRow {
  doubt_session_id: string
  turn_index: number
  student_message: string
  ai_response: string
  validation_score: number | null
  appropriateness: number | null
  restart_detected: boolean
  single_question: boolean
  judge_rationale: string
  subject?: string
  hint_level?: number
}

// ── Animation helpers ─────────────────────────────────────────────────────────

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1]
const fadeUp = { hidden: { opacity: 0, y: 16 }, visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } } }
const stagger = { hidden: {}, visible: { transition: { staggerChildren: 0.06 } } }

// ── Shared components ─────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, color = 'slate', icon: Icon,
}: {
  label: string; value: string | number; sub?: string; color?: string; icon?: React.ElementType
}) {
  const accent = {
    slate: 'from-slate-500/10 to-slate-500/5',
    green: 'from-emerald-500/10 to-emerald-500/5',
    amber: 'from-amber-500/10 to-amber-500/5',
    red:   'from-red-500/10 to-red-500/5',
    purple:'from-purple-500/10 to-purple-500/5',
    blue:  'from-blue-500/10 to-blue-500/5',
  }[color] ?? 'from-slate-500/10 to-slate-500/5'
  return (
    <motion.div variants={fadeUp}
      className={`bg-gradient-to-br ${accent} border border-white/70 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)] backdrop-blur-sm`}>
      <div className="flex items-start justify-between mb-2">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{label}</p>
        {Icon && <Icon className="w-4 h-4 text-slate-400" />}
      </div>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </motion.div>
  )
}

function ScoreBadge({ value, max = 2 }: { value: number | null; max?: number }) {
  if (value === null) return <span className="text-slate-400 text-xs">–</span>
  const ratio = value / max
  const cls = ratio >= 0.8 ? 'bg-emerald-100 text-emerald-700' : ratio >= 0.5 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>{value}/{max}</span>
}

function BoolBadge({ value, goodWhen }: { value: boolean; goodWhen: boolean }) {
  const ok = value === goodWhen
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${ok ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
      {ok ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {value ? 'YES' : 'NO'}
    </span>
  )
}

function TurnCard({ turn }: { turn: TurnRow }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="bg-white/80 border border-slate-100 rounded-xl p-4 shadow-[0_2px_12px_rgb(0,0,0,0.04)]">
      <div className="flex flex-wrap gap-2 mb-3">
        <ScoreBadge value={turn.validation_score} />
        <ScoreBadge value={turn.appropriateness} />
        <span className="text-xs text-slate-500 font-medium">Restart:</span>
        <BoolBadge value={turn.restart_detected} goodWhen={false} />
        <span className="text-xs text-slate-500 font-medium">Single-Q:</span>
        <BoolBadge value={turn.single_question} goodWhen={true} />
        {turn.subject && <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium">{turn.subject}</span>}
      </div>
      <div className="space-y-2 text-sm">
        <div className="bg-slate-50 rounded-lg p-3">
          <p className="text-xs font-semibold text-slate-400 mb-1">STUDENT</p>
          <p className="text-slate-700">{turn.student_message.slice(0, 200)}{turn.student_message.length > 200 ? '…' : ''}</p>
        </div>
        <div className={`bg-purple-50 rounded-lg p-3 overflow-hidden transition-all duration-300 ${expanded ? '' : 'max-h-20'}`}>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-semibold text-purple-400">AI TUTOR</p>
            <button onClick={() => setExpanded(!expanded)} className="text-xs text-purple-400 hover:text-purple-600 flex items-center gap-1">
              {expanded ? <><ChevronUp className="w-3 h-3" />Collapse</> : <><ChevronDown className="w-3 h-3" />Expand</>}
            </button>
          </div>
          <p className="text-slate-700 whitespace-pre-wrap">{turn.ai_response}</p>
        </div>
      </div>
      {turn.judge_rationale && (
        <p className="text-xs text-slate-400 italic mt-2">{turn.judge_rationale}</p>
      )}
    </div>
  )
}

const SECTION_COLORS = ['#6366f1','#8b5cf6','#06b6d4','#f59e0b','#ec4899','#10b981','#3b82f6','#ef4444']
const PIE_COLORS: Record<string, string> = { Physics: '#6366f1', Chemistry: '#06b6d4', Maths: '#10b981' }

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const router = useRouter()
  const [authChecked, setAuthChecked] = useState(false)
  const [authDenied, setAuthDenied] = useState(false)
  const [activeSection, setActiveSection] = useState<Section>('platform')

  // Section data
  const [platformData, setPlatformData]     = useState<any>(null)
  const [convQuality, setConvQuality]       = useState<any>(null)
  const [respQuality, setRespQuality]       = useState<any>(null)
  const [sysPerf, setSysPerf]               = useState<any>(null)
  const [feedbackData, setFeedbackData]     = useState<any>(null)
  const [kbData, setKbData]                 = useState<any>(null)
  const [studentsData, setStudentsData]     = useState<any>(null)
  const [diagnosticsData, setDiagnosticsData] = useState<any>(null)
  const [digestData, setDigestData]         = useState<any>(null)

  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [days, setDays] = useState(7)

  const setLoad = (key: string, val: boolean) =>
    setLoading(prev => ({ ...prev, [key]: val }))

  // ── Auth guard ─────────────────────────────────────────────────────────────
  useEffect(() => {
    apiGet('/admin/is_admin')
      .then((d: any) => {
        if (!d.is_admin) setAuthDenied(true)
        else setAuthChecked(true)
      })
      .catch(() => router.replace('/auth/login'))
  }, [router])

  // ── Data loaders ───────────────────────────────────────────────────────────
  const loadPlatform = useCallback(async () => {
    setLoad('platform', true)
    try { setPlatformData(await apiGet(`/admin/platform-health?days=${days}`)) } finally { setLoad('platform', false) }
  }, [days])

  const loadConvQuality = useCallback(async () => {
    setLoad('conv', true)
    try { setConvQuality(await apiGet(`/admin/conversation-quality?days=${days}`)) } finally { setLoad('conv', false) }
  }, [days])

  const loadRespQuality = useCallback(async () => {
    setLoad('resp', true)
    try { setRespQuality(await apiGet(`/admin/response-quality?days=${days}`)) } finally { setLoad('resp', false) }
  }, [days])

  const loadSysPerf = useCallback(async () => {
    setLoad('sys', true)
    try { setSysPerf(await apiGet(`/admin/system-performance?days=${days}`)) } finally { setLoad('sys', false) }
  }, [days])

  const loadFeedback = useCallback(async () => {
    setLoad('feed', true)
    try { setFeedbackData(await apiGet(`/admin/user-feedback?days=${days}`)) } finally { setLoad('feed', false) }
  }, [days])

  const loadKb = useCallback(async () => {
    setLoad('kb', true)
    try { setKbData(await apiGet('/admin/knowledge-base')) } finally { setLoad('kb', false) }
  }, [])

  const loadStudents = useCallback(async () => {
    setLoad('students', true)
    try { setStudentsData(await apiGet(`/admin/student-insights?days=30`)) } finally { setLoad('students', false) }
  }, [])

  const runDiagnostics = useCallback(async () => {
    setLoad('diag', true)
    try { setDiagnosticsData(await apiPost('/admin/diagnostics', {})) } finally { setLoad('diag', false) }
  }, [])

  const runDigest = useCallback(async () => {
    setLoad('digest', true)
    try { setDigestData(await apiPost('/admin/quality-digest', {})) } finally { setLoad('digest', false) }
  }, [])

  // Load data when section changes
  useEffect(() => {
    if (!authChecked) return
    if (activeSection === 'platform' && !platformData)       loadPlatform()
    if (activeSection === 'conv-quality' && !convQuality)    loadConvQuality()
    if (activeSection === 'response-quality' && !respQuality) loadRespQuality()
    if (activeSection === 'system-perf' && !sysPerf)         loadSysPerf()
    if (activeSection === 'feedback' && !feedbackData)        loadFeedback()
    if (activeSection === 'knowledge' && !kbData)             loadKb()
    if (activeSection === 'students' && !studentsData)        loadStudents()
  }, [activeSection, authChecked]) // eslint-disable-line

  if (authDenied) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="max-w-md w-full rounded-2xl bg-white border border-red-100 shadow-lg p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center mx-auto">
            <XCircle className="w-7 h-7 text-red-500" />
          </div>
          <h1 className="text-xl font-semibold text-slate-800">Admin access not configured</h1>
          <p className="text-sm text-slate-500 leading-relaxed">
            Your account is not in the admin list. Add your email to Render environment variables:
          </p>
          <code className="block bg-slate-900 text-green-400 rounded-lg px-4 py-3 text-sm font-mono text-left">
            ADMIN_EMAILS=srivastava.ish@northeastern.edu
          </code>
          <p className="text-xs text-slate-400">
            Render → upmyrank-api → Environment → Add Variable → Redeploy
          </p>
          <button
            onClick={() => router.replace('/')}
            className="mt-2 text-sm text-purple-600 hover:underline"
          >
            ← Back to dashboard
          </button>
        </div>
      </div>
    )
  }

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
      </div>
    )
  }

  // ── Sidebar nav config ─────────────────────────────────────────────────────
  const NAV: { id: Section; label: string; icon: React.ElementType }[] = [
    { id: 'platform',         label: 'Platform Health',       icon: Globe },
    { id: 'conv-quality',     label: 'Conv. Quality',         icon: MessageSquare },
    { id: 'response-quality', label: 'Response Quality',      icon: Star },
    { id: 'system-perf',      label: 'System Perf.',          icon: Zap },
    { id: 'feedback',         label: 'User Feedback',         icon: ThumbsUp },
    { id: 'knowledge',        label: 'Knowledge Base',        icon: BookOpen },
    { id: 'students',         label: 'Student Insights',      icon: Users },
    { id: 'diagnostics',      label: 'Diagnostics',           icon: Stethoscope },
  ]

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50/30 to-slate-100 flex">

      {/* Left sidebar */}
      <aside className="fixed top-0 left-0 h-full w-52 bg-white/90 backdrop-blur-md border-r border-slate-100 flex flex-col z-30 shadow-[4px_0_24px_rgb(0,0,0,0.04)]">
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center">
              <BarChart2 className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">Admin</p>
              <p className="text-xs text-slate-400">UpMyRank</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV.map(({ id, label, icon: Icon }) => {
            const active = activeSection === id
            return (
              <button
                key={id}
                onClick={() => setActiveSection(id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 text-left
                  ${active
                    ? 'bg-purple-600 text-white shadow-[0_4px_12px_rgba(124,58,237,0.35)]'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {label}
              </button>
            )
          })}
        </nav>

        {/* Days filter */}
        <div className="px-4 py-4 border-t border-slate-100">
          <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Lookback</p>
          <div className="flex gap-1.5 flex-wrap">
            {[7, 14, 30].map(d => (
              <button
                key={d}
                onClick={() => {
                  setDays(d)
                  setPlatformData(null); setConvQuality(null); setRespQuality(null)
                  setSysPerf(null); setFeedbackData(null)
                }}
                className={`text-xs px-2.5 py-1 rounded-lg font-semibold transition-all ${
                  days === d ? 'bg-purple-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-52 flex-1 p-6 min-h-screen">
        <AnimatePresence mode="wait">
          <motion.div key={activeSection} initial="hidden" animate="visible" exit="hidden" variants={stagger}>

            {/* ── PLATFORM HEALTH ──────────────────────────────────────────── */}
            {activeSection === 'platform' && (
              <Section title="Platform Health" icon={Globe} onRefresh={loadPlatform} loading={!!loading.platform}>
                {platformData ? (
                  <>
                    <motion.div variants={stagger} className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
                      <StatCard label="Total Students" value={platformData.total_students} icon={Users} color="purple" />
                      <StatCard label="Total Sessions" value={platformData.total_sessions} icon={Activity} color="blue" />
                      <StatCard label="Total Doubts" value={platformData.total_doubts} icon={MessageSquare} color="indigo" />
                      <StatCard label="Active Today" value={platformData.active_today} icon={TrendingUp} color="green" />
                      <StatCard label="Active This Week" value={platformData.active_this_week} icon={TrendingUp} color="green" />
                      <StatCard label="Onboarding Rate" value={`${(platformData.onboarding_completion_rate * 100).toFixed(0)}%`} icon={CheckCircle2} color={platformData.onboarding_completion_rate > 0.7 ? 'green' : 'amber'} />
                    </motion.div>

                    <motion.div variants={stagger} className="grid grid-cols-3 gap-4 mb-6">
                      <StatCard label="Day-1 Retention" value={`${(platformData.retention_day1 * 100).toFixed(0)}%`} sub="Had session in first 2 days" color={platformData.retention_day1 > 0.4 ? 'green' : 'amber'} />
                      <StatCard label="Day-7 Retention" value={`${(platformData.retention_day7 * 100).toFixed(0)}%`} sub="Had session after 7+ days" color={platformData.retention_day7 > 0.3 ? 'green' : 'amber'} />
                      <StatCard label="Avg Doubts/Session" value={platformData.avg_doubts_per_session?.toFixed(1) ?? '–'} sub={`Avg session: ${platformData.avg_session_length_minutes?.toFixed(0) ?? '–'} min`} />
                    </motion.div>

                    {/* Sessions per day chart */}
                    <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                      <h3 className="text-sm font-semibold text-slate-700 mb-4">Sessions per Day (last 14 days)</h3>
                      <ResponsiveContainer width="100%" height={180}>
                        <AreaChart data={[...platformData.sessions_per_day].reverse()}>
                          <defs>
                            <linearGradient id="spd" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.3} />
                              <stop offset="100%" stopColor="#7c3aed" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                          <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                          <Area type="monotone" dataKey="count" stroke="#7c3aed" fill="url(#spd)" strokeWidth={2} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </motion.div>

                    {/* Subject distribution */}
                    {Object.keys(platformData.subject_distribution || {}).length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Subject Distribution (% of doubts)</h3>
                        <div className="flex items-center gap-8">
                          <PieChart width={160} height={160}>
                            <Pie data={Object.entries(platformData.subject_distribution).map(([k, v]: any) => ({ name: k, value: Math.round(v * 100) }))}
                              cx={75} cy={75} innerRadius={45} outerRadius={70} dataKey="value">
                              {Object.keys(platformData.subject_distribution).map((k) => (
                                <Cell key={k} fill={PIE_COLORS[k] ?? '#94a3b8'} />
                              ))}
                            </Pie>
                            <Tooltip formatter={(v: unknown) => `${v}%`} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                          </PieChart>
                          <div className="space-y-2">
                            {Object.entries(platformData.subject_distribution).map(([subj, pct]: any) => (
                              <div key={subj} className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: PIE_COLORS[subj] ?? '#94a3b8' }} />
                                <span className="text-sm text-slate-700 font-medium">{subj}</span>
                                <span className="text-sm text-slate-500">{(pct * 100).toFixed(1)}%</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </>
                ) : <LoadingState />}
              </Section>
            )}

            {/* ── CONVERSATION QUALITY ─────────────────────────────────────── */}
            {activeSection === 'conv-quality' && (
              <Section title="Conversation Quality" icon={MessageSquare} onRefresh={loadConvQuality} loading={!!loading.conv}>
                {convQuality ? (
                  <>
                    <motion.div variants={stagger} className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                      <StatCard label="Avg Validation" value={convQuality.avg_validation_score?.toFixed(2) ?? '–'} sub="Target: ≥1.5 / 2" color={convQuality.avg_validation_score >= 1.5 ? 'green' : 'red'} />
                      <StatCard label="Avg Appropriateness" value={convQuality.avg_appropriateness?.toFixed(2) ?? '–'} sub="Target: ≥1.5 / 2" color={convQuality.avg_appropriateness >= 1.5 ? 'green' : 'amber'} />
                      <StatCard label="Restart Rate" value={`${convQuality.restart_rate_pct?.toFixed(1) ?? '–'}%`} sub="Lower is better" color={convQuality.restart_rate_pct > 20 ? 'red' : convQuality.restart_rate_pct > 10 ? 'amber' : 'green'} icon={TrendingDown} />
                      <StatCard label="Single-Q Compliance" value={`${convQuality.single_q_compliance_pct?.toFixed(1) ?? '–'}%`} sub="Target: ≥90%" color={convQuality.single_q_compliance_pct >= 90 ? 'green' : 'amber'} icon={CheckCircle2} />
                    </motion.div>

                    {/* Quality trend */}
                    {convQuality.quality_trend?.length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Quality Trend (daily avg)</h3>
                        <ResponsiveContainer width="100%" height={180}>
                          <LineChart data={convQuality.quality_trend}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <YAxis domain={[0, 2]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                            <Legend wrapperStyle={{ fontSize: 12 }} />
                            <Line type="monotone" dataKey="avg_validation" name="Validation" stroke="#7c3aed" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="avg_appropriateness" name="Appropriateness" stroke="#06b6d4" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </motion.div>
                    )}

                    {/* Worst turns */}
                    <TurnList title="Worst Turns" turns={convQuality.worst_turns ?? []} defaultOpen />

                    {/* Best turns */}
                    <TurnList title="Best Turns" turns={convQuality.best_turns ?? []} />

                    {/* Digest */}
                    <motion.div variants={fadeUp} className="mt-6 bg-white/80 border border-slate-100 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <h3 className="text-sm font-semibold text-slate-700">Quality Digest</h3>
                          <p className="text-xs text-slate-400 mt-0.5">AI-generated analysis of worst turns</p>
                        </div>
                        <button onClick={runDigest} disabled={!!loading.digest}
                          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-xl text-sm font-semibold shadow-[0_4px_12px_rgba(124,58,237,0.35)] hover:bg-purple-700 transition-all disabled:opacity-50 active:scale-95">
                          {loading.digest ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                          {loading.digest ? 'Generating…' : 'Generate Digest'}
                        </button>
                      </div>
                      {digestData && (
                        <div className="space-y-3">
                          {digestData.main_pattern && (
                            <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                              <p className="text-xs font-semibold text-amber-600 mb-1">MAIN PATTERN</p>
                              <p className="text-sm text-slate-700">{digestData.main_pattern}</p>
                            </div>
                          )}
                          {digestData.top_fix && (
                            <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4">
                              <p className="text-xs font-semibold text-emerald-600 mb-1">TOP FIX</p>
                              <p className="text-sm text-slate-700">{digestData.top_fix}</p>
                            </div>
                          )}
                          {digestData.diagnosis && (
                            <div className="bg-slate-50 border border-slate-100 rounded-xl p-4">
                              <p className="text-xs font-semibold text-slate-400 mb-1">FULL DIAGNOSIS</p>
                              <p className="text-sm text-slate-600 leading-relaxed">{digestData.diagnosis}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </motion.div>
                  </>
                ) : <LoadingState />}
              </Section>
            )}

            {/* ── RESPONSE QUALITY ─────────────────────────────────────────── */}
            {activeSection === 'response-quality' && (
              <Section title="Response Quality (4-Dim Judge)" icon={Star} onRefresh={loadRespQuality} loading={!!loading.resp}>
                {respQuality ? (
                  <>
                    <motion.div variants={stagger} className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                      {[
                        { label: 'Pedagogical', key: 'avg_pedagogical', max: 2 },
                        { label: 'Factual', key: 'avg_factual', max: 1 },
                        { label: 'Context Relevance', key: 'avg_context_relevance', max: 1 },
                        { label: 'Hint Appropriateness', key: 'avg_hint_appropriateness', max: 1 },
                      ].map(({ label, key, max }) => {
                        const val = respQuality[key]
                        const ratio = val != null ? val / max : null
                        const color = ratio == null ? 'slate' : ratio >= 0.8 ? 'green' : ratio >= 0.5 ? 'amber' : 'red'
                        return (
                          <StatCard key={key} label={label} value={val != null ? val.toFixed(2) : '–'} sub={`/ ${max} max`} color={color} />
                        )
                      })}
                    </motion.div>

                    {/* By subject */}
                    {Object.keys(respQuality.by_subject ?? {}).length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">By Subject</h3>
                        <div className="grid grid-cols-3 gap-4">
                          {Object.entries(respQuality.by_subject).map(([subj, d]: any) => (
                            <div key={subj} className="bg-slate-50 rounded-xl p-4">
                              <p className="text-sm font-bold text-slate-800 mb-2" style={{ color: PIE_COLORS[subj] ?? '#64748b' }}>{subj}</p>
                              <div className="space-y-1 text-xs text-slate-600">
                                <div className="flex justify-between"><span>Pedagogical</span><span className="font-semibold">{d.avg_pedagogical?.toFixed(2) ?? '–'}</span></div>
                                <div className="flex justify-between"><span>Factual</span><span className="font-semibold">{d.avg_factual?.toFixed(2) ?? '–'}</span></div>
                                <div className="flex justify-between"><span>Overall</span><span className="font-semibold">{d.avg_overall?.toFixed(2) ?? '–'}</span></div>
                                <div className="flex justify-between text-slate-400"><span>Evaluations</span><span>{d.count}</span></div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}

                    {/* Trend */}
                    {respQuality.score_trend?.length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Overall Score Trend</h3>
                        <ResponsiveContainer width="100%" height={180}>
                          <LineChart data={respQuality.score_trend}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                            <Line type="monotone" dataKey="avg_overall" stroke="#7c3aed" strokeWidth={2} dot={false} name="Overall" />
                          </LineChart>
                        </ResponsiveContainer>
                      </motion.div>
                    )}
                    {respQuality.total_evaluated === 0 && (
                      <EmptyState message="No judge evaluations yet. End a study session to trigger evaluation." />
                    )}
                  </>
                ) : <LoadingState />}
              </Section>
            )}

            {/* ── SYSTEM PERFORMANCE ───────────────────────────────────────── */}
            {activeSection === 'system-perf' && (
              <Section title="System Performance" icon={Zap} onRefresh={loadSysPerf} loading={!!loading.sys}>
                {sysPerf ? (
                  <>
                    <motion.div variants={stagger} className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
                      {[
                        { label: 'Retrieval P50', value: sysPerf.retrieval_latency_p50, color: 'blue' },
                        { label: 'Retrieval P95', value: sysPerf.retrieval_latency_p95, color: sysPerf.retrieval_latency_p95 > 3000 ? 'amber' : 'green' },
                        { label: 'Retrieval P99', value: sysPerf.retrieval_latency_p99, color: sysPerf.retrieval_latency_p99 > 8000 ? 'red' : 'slate' },
                        { label: 'LLM P50', value: sysPerf.llm_latency_p50, color: 'blue' },
                        { label: 'LLM P95', value: sysPerf.llm_latency_p95, color: sysPerf.llm_latency_p95 > 5000 ? 'amber' : 'green' },
                        { label: 'LLM P99', value: sysPerf.llm_latency_p99, color: sysPerf.llm_latency_p99 > 10000 ? 'red' : 'slate' },
                      ].map(({ label, value, color }) => (
                        <StatCard key={label} label={label} value={value != null ? `${value}ms` : '–'} color={color as any} icon={Clock} />
                      ))}
                    </motion.div>

                    {/* Agent steps distribution */}
                    {Object.keys(sysPerf.agent_steps_distribution ?? {}).length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Agent Steps Distribution</h3>
                        <ResponsiveContainer width="100%" height={160}>
                          <BarChart data={Object.entries(sysPerf.agent_steps_distribution).map(([k, v]: any) => ({ steps: `${k} step${k !== '1' ? 's' : ''}`, count: v }))}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="steps" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                            <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </motion.div>
                    )}

                    {/* Latency trend */}
                    {sysPerf.latency_trend?.length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Daily Latency Trend</h3>
                        <ResponsiveContainer width="100%" height={180}>
                          <LineChart data={sysPerf.latency_trend}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                            <Legend wrapperStyle={{ fontSize: 12 }} />
                            <Line type="monotone" dataKey="avg_retrieval_ms" name="Retrieval" stroke="#6366f1" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="avg_llm_ms" name="LLM" stroke="#f59e0b" strokeWidth={2} dot={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </motion.div>
                    )}

                    {/* Slowest sessions */}
                    {sysPerf.slowest_sessions?.length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Slowest Sessions</h3>
                        <div className="space-y-2">
                          {sysPerf.slowest_sessions.map((s: any, i: number) => (
                            <div key={i} className="flex items-center justify-between bg-slate-50 rounded-xl px-4 py-3 text-sm">
                              <span className="text-slate-500 font-mono text-xs truncate max-w-[200px]">{s.doubt_session_id}</span>
                              <span className="text-slate-500">{s.subject ?? '–'}</span>
                              <span className={`font-bold ${s.retrieval_latency_ms > 8000 ? 'text-red-500' : 'text-amber-500'}`}>{s.retrieval_latency_ms}ms</span>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </>
                ) : <LoadingState />}
              </Section>
            )}

            {/* ── USER FEEDBACK ─────────────────────────────────────────────── */}
            {activeSection === 'feedback' && (
              <Section title="User Feedback" icon={ThumbsUp} onRefresh={loadFeedback} loading={!!loading.feed}>
                {feedbackData ? (
                  <>
                    <motion.div variants={stagger} className="grid grid-cols-3 gap-4 mb-6">
                      <StatCard label="Total Feedback" value={feedbackData.total_feedback} icon={ThumbsUp} />
                      <StatCard label="Thumbs Up" value={`${feedbackData.thumbs_up_pct?.toFixed(1) ?? '–'}%`} sub={`${feedbackData.thumbs_up_count} responses`} color="green" icon={TrendingUp} />
                      <StatCard label="No Feedback" value={feedbackData.students_without_feedback} sub="Students with sessions but no feedback" color={feedbackData.students_without_feedback > 5 ? 'amber' : 'slate'} />
                    </motion.div>

                    {/* Sentiment bar */}
                    {feedbackData.total_feedback > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-3">Overall Sentiment</h3>
                        <div className="flex rounded-xl overflow-hidden h-8">
                          <div className="bg-emerald-400 flex items-center justify-center text-white text-xs font-bold"
                            style={{ width: `${feedbackData.thumbs_up_pct}%` }}>
                            {feedbackData.thumbs_up_pct > 10 ? `${feedbackData.thumbs_up_pct.toFixed(0)}% 👍` : ''}
                          </div>
                          <div className="bg-red-300 flex items-center justify-center text-white text-xs font-bold flex-1">
                            {(100 - feedbackData.thumbs_up_pct) > 10 ? `${(100 - feedbackData.thumbs_up_pct).toFixed(0)}% 👎` : ''}
                          </div>
                        </div>
                      </motion.div>
                    )}

                    {/* By subject */}
                    {Object.keys(feedbackData.by_subject ?? {}).length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">By Subject</h3>
                        <div className="space-y-3">
                          {Object.entries(feedbackData.by_subject).map(([subj, d]: any) => {
                            const total = d.thumbs_up + d.thumbs_down
                            const pct = total > 0 ? Math.round(d.thumbs_up / total * 100) : 0
                            return (
                              <div key={subj} className="flex items-center gap-4">
                                <span className="w-20 text-sm font-medium text-slate-700">{subj}</span>
                                <div className="flex-1 rounded-full h-3 bg-slate-100 overflow-hidden">
                                  <div className="h-full bg-emerald-400 rounded-full transition-all" style={{ width: `${pct}%` }} />
                                </div>
                                <span className="text-sm text-slate-500 w-16 text-right">{pct}% 👍</span>
                              </div>
                            )
                          })}
                        </div>
                      </motion.div>
                    )}

                    {feedbackData.judge_thumbs_correlation != null && (
                      <motion.div variants={fadeUp} className="bg-blue-50 border border-blue-100 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <p className="text-sm font-semibold text-blue-700">Judge–Thumbs Correlation: <span className="text-blue-900">{(feedbackData.judge_thumbs_correlation * 100).toFixed(0)}%</span></p>
                        <p className="text-xs text-blue-500 mt-1">Pearson r between judge overall_score and thumbs rating. Higher = judge aligns with student sentiment.</p>
                      </motion.div>
                    )}

                    {feedbackData.total_feedback === 0 && (
                      <EmptyState message="No feedback yet. Thumbs up/down buttons appear on AI messages in the doubt chat." />
                    )}
                  </>
                ) : <LoadingState />}
              </Section>
            )}

            {/* ── KNOWLEDGE BASE ───────────────────────────────────────────── */}
            {activeSection === 'knowledge' && (
              <Section title="Knowledge Base" icon={BookOpen} onRefresh={loadKb} loading={!!loading.kb}>
                {kbData ? (
                  <>
                    <motion.div variants={stagger} className="grid grid-cols-3 gap-4 mb-6">
                      <StatCard label="Total Chunks" value={kbData.total_chunks.toLocaleString()} icon={Database} color="purple" />
                      <StatCard label="JEE Problems" value={kbData.jee_problems_count} sub="Physics + Chemistry + Maths" color={kbData.jee_problems_count < 50 ? 'amber' : 'green'} />
                      <StatCard label="Null Embeddings" value={kbData.null_embeddings_count} sub={kbData.null_embeddings_count > 0 ? 'Re-ingest needed' : 'All good'} color={kbData.null_embeddings_count > 0 ? 'red' : 'green'} icon={AlertTriangle} />
                    </motion.div>

                    {/* Per-subject breakdown */}
                    <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                      <h3 className="text-sm font-semibold text-slate-700 mb-4">Chunks by Subject</h3>
                      <ResponsiveContainer width="100%" height={160}>
                        <BarChart data={Object.entries(kbData.by_subject).map(([k, v]: any) => ({ subject: k, count: v.count }))}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="subject" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                          <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                          <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                            {Object.keys(kbData.by_subject).map((k: string) => (
                              <Cell key={k} fill={PIE_COLORS[k] ?? '#94a3b8'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </motion.div>

                    {/* Chapter breakdown per subject */}
                    {Object.entries(kbData.by_subject).map(([subj, data]: any) => (
                      <SubjectChapterAccordion key={subj} subject={subj} chapters={data.chapters} />
                    ))}

                    {kbData.jee_problems_count < 50 && (
                      <motion.div variants={fadeUp} className="mt-4 bg-amber-50 border border-amber-200 rounded-2xl p-4">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-500" />
                          <p className="text-sm text-amber-700 font-medium">Low JEE Problem Coverage</p>
                        </div>
                        <p className="text-xs text-amber-600 mt-1">Only {kbData.jee_problems_count} problems — target is 100+. Run scripts/ingest_jee_pyq.py to expand.</p>
                      </motion.div>
                    )}
                  </>
                ) : <LoadingState />}
              </Section>
            )}

            {/* ── STUDENT INSIGHTS ─────────────────────────────────────────── */}
            {activeSection === 'students' && (
              <Section title="Student Insights (30d)" icon={Users} onRefresh={loadStudents} loading={!!loading.students}>
                {studentsData ? (
                  <>
                    <motion.div variants={stagger} className="grid grid-cols-3 gap-4 mb-6">
                      <StatCard label="Total Students" value={studentsData.total_students} icon={Users} color="purple" />
                      <StatCard label="Avg Mastery" value={studentsData.avg_mastery_score != null ? `${(studentsData.avg_mastery_score * 100).toFixed(0)}%` : '–'} sub="Across all concepts" color={studentsData.avg_mastery_score > 0.5 ? 'green' : 'amber'} />
                      <StatCard label="Stuck Students" value={studentsData.stuck_students?.length ?? 0} sub="3+ sessions on same topic" color={studentsData.stuck_students?.length > 0 ? 'amber' : 'green'} icon={AlertTriangle} />
                    </motion.div>

                    {/* Mastery by subject */}
                    {Object.keys(studentsData.mastery_by_subject ?? {}).length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Average Mastery by Subject</h3>
                        <div className="space-y-3">
                          {Object.entries(studentsData.mastery_by_subject).map(([subj, score]: any) => (
                            <div key={subj} className="flex items-center gap-4">
                              <span className="w-20 text-sm font-medium text-slate-700">{subj}</span>
                              <div className="flex-1 bg-slate-100 rounded-full h-3 overflow-hidden">
                                <div className="h-full rounded-full transition-all" style={{ width: `${(score ?? 0) * 100}%`, background: PIE_COLORS[subj] ?? '#94a3b8' }} />
                              </div>
                              <span className="text-sm text-slate-600 w-12 text-right">{score != null ? `${(score * 100).toFixed(0)}%` : '–'}</span>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}

                    {/* Stuck students */}
                    {studentsData.stuck_students?.length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 mb-6 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Stuck Students</h3>
                        <div className="space-y-2">
                          {studentsData.stuck_students.map((s: any, i: number) => (
                            <div key={i} className="flex items-center justify-between bg-amber-50 rounded-xl px-4 py-3 text-sm">
                              <span className="font-mono text-xs text-slate-500 truncate max-w-[180px]">{s.student_id}</span>
                              <span className="font-medium text-slate-700 truncate max-w-[200px]">{s.topic}</span>
                              <span className="text-amber-600 font-bold">{s.session_count} sessions</span>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}

                    {/* Hint escalation */}
                    {studentsData.hint_escalation_by_topic?.length > 0 && (
                      <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)]">
                        <h3 className="text-sm font-semibold text-slate-700 mb-4">Hint Escalation by Topic</h3>
                        <ResponsiveContainer width="100%" height={220}>
                          <BarChart data={studentsData.hint_escalation_by_topic.slice(0, 10)} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                            <XAxis type="number" domain={[0, 4]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                            <YAxis dataKey="topic" type="category" tick={{ fontSize: 10, fill: '#64748b' }} width={130} />
                            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                            <Bar dataKey="avg_max_hint_level" name="Avg Max Hint Level" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </motion.div>
                    )}
                  </>
                ) : <LoadingState />}
              </Section>
            )}

            {/* ── DIAGNOSTICS ───────────────────────────────────────────────── */}
            {activeSection === 'diagnostics' && (
              <Section title="System Diagnostics" icon={Stethoscope} onRefresh={() => {}} loading={false}>
                <motion.div variants={fadeUp} className="mb-6">
                  <button onClick={runDiagnostics} disabled={!!loading.diag}
                    className="flex items-center gap-3 px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-2xl text-sm font-bold shadow-[0_8px_24px_rgba(124,58,237,0.4)] hover:shadow-[0_12px_32px_rgba(124,58,237,0.5)] transition-all active:scale-95 disabled:opacity-50">
                    {loading.diag ? <Loader2 className="w-5 h-5 animate-spin" /> : <Stethoscope className="w-5 h-5" />}
                    {loading.diag ? 'Running checks…' : 'Run Diagnostics'}
                  </button>
                  <p className="text-xs text-slate-400 mt-2">Checks all tables, Redis, latency, and data pipeline health.</p>
                </motion.div>

                {diagnosticsData && (
                  <motion.div variants={stagger}>
                    {/* Status banner */}
                    <motion.div variants={fadeUp} className={`flex items-center gap-3 p-4 rounded-2xl mb-6 font-semibold text-sm ${
                      diagnosticsData.status === 'ok' ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' :
                      diagnosticsData.status === 'warning' ? 'bg-amber-50 border border-amber-200 text-amber-700' :
                      'bg-red-50 border border-red-200 text-red-700'
                    }`}>
                      {diagnosticsData.status === 'ok' ? <CheckCircle2 className="w-5 h-5" /> :
                       diagnosticsData.status === 'warning' ? <AlertTriangle className="w-5 h-5" /> :
                       <XCircle className="w-5 h-5" />}
                      Overall status: {diagnosticsData.status.toUpperCase()} — checked at {new Date(diagnosticsData.ran_at).toLocaleTimeString()}
                    </motion.div>

                    {/* Individual checks */}
                    <motion.div variants={stagger} className="space-y-2">
                      {diagnosticsData.checks.map((c: any) => (
                        <motion.div key={c.name} variants={fadeUp}
                          className="flex items-start gap-3 bg-white/80 border border-slate-100 rounded-xl px-4 py-3 shadow-[0_2px_8px_rgb(0,0,0,0.03)]">
                          <div className="mt-0.5">
                            {c.status === 'ok' && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                            {c.status === 'warning' && <AlertTriangle className="w-4 h-4 text-amber-500" />}
                            {c.status === 'error' && <XCircle className="w-4 h-4 text-red-500" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-slate-700">{c.name.replace(/_/g, ' ')}</p>
                            <p className="text-xs text-slate-400 mt-0.5">{c.detail}</p>
                          </div>
                        </motion.div>
                      ))}
                    </motion.div>
                  </motion.div>
                )}
              </Section>
            )}

          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Section({
  title, icon: Icon, children, onRefresh, loading,
}: {
  title: string; icon: React.ElementType; children: React.ReactNode; onRefresh: () => void; loading: boolean
}) {
  return (
    <>
      <motion.div variants={fadeUp} className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-100 to-indigo-100 flex items-center justify-center">
            <Icon className="w-5 h-5 text-purple-600" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">{title}</h1>
        </div>
        <button onClick={onRefresh} disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-600 hover:border-purple-300 hover:text-purple-600 transition-all active:scale-95 disabled:opacity-40 shadow-[0_2px_8px_rgb(0,0,0,0.04)]">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </motion.div>
      {children}
    </>
  )
}

function LoadingState() {
  return (
    <motion.div variants={fadeUp} className="flex items-center justify-center py-24">
      <div className="text-center">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin mx-auto mb-3" />
        <p className="text-sm text-slate-400">Loading data…</p>
      </div>
    </motion.div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <motion.div variants={fadeUp} className="flex items-center justify-center py-16 bg-white/60 rounded-2xl border border-dashed border-slate-200">
      <div className="text-center px-6">
        <Minus className="w-8 h-8 text-slate-300 mx-auto mb-3" />
        <p className="text-sm text-slate-400 max-w-xs">{message}</p>
      </div>
    </motion.div>
  )
}

function TurnList({ title, turns, defaultOpen = false }: { title: string; turns: TurnRow[]; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl shadow-[0_4px_20px_rgb(0,0,0,0.04)] mb-6">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left">
        <h3 className="text-sm font-semibold text-slate-700">{title} ({turns.length})</h3>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      <AnimatePresence>
        {open && turns.length > 0 && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden">
            <div className="px-5 pb-5 space-y-4">
              {turns.map((t, i) => <TurnCard key={i} turn={t} />)}
            </div>
          </motion.div>
        )}
        {open && turns.length === 0 && (
          <div className="px-5 pb-5">
            <EmptyState message="No turns in this category for the selected period." />
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function SubjectChapterAccordion({ subject, chapters }: { subject: string; chapters: { chapter: string; count: number }[] }) {
  const [open, setOpen] = useState(false)
  return (
    <motion.div variants={fadeUp} className="bg-white/80 border border-slate-100 rounded-2xl shadow-[0_4px_20px_rgb(0,0,0,0.04)] mb-4">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full" style={{ background: PIE_COLORS[subject] ?? '#94a3b8' }} />
          <span className="text-sm font-semibold text-slate-700">{subject}</span>
          <span className="text-xs text-slate-400">{chapters.reduce((a, c) => a + c.count, 0).toLocaleString()} chunks</span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="px-5 pb-4 grid grid-cols-2 gap-2">
              {chapters.map((c, i) => (
                <div key={i} className="flex justify-between items-center bg-slate-50 rounded-lg px-3 py-2 text-xs">
                  <span className="text-slate-600 truncate max-w-[160px]">{c.chapter}</span>
                  <span className="font-semibold text-slate-800 ml-2">{c.count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
