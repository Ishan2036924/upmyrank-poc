'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  User, BarChart3, Settings2, SlidersHorizontal,
  RefreshCw, Lock, AlertTriangle, CheckCircle2, TrendingUp,
  Zap, Target, BookOpen, Star,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
  RadialBarChart, RadialBar, Legend,
} from 'recharts'
import Sidebar from '@/components/Sidebar'
import AuthGuard from '@/components/AuthGuard'
import { apiGet } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { StudentGenome, PersonaProfile } from '@/lib/types'
import { SYLLABUS_MAP } from '@/lib/syllabus'

// ── Types ─────────────────────────────────────────────────────────────────────

type TabId = 'profile' | 'analytics' | 'preferences'

// ── Constants ─────────────────────────────────────────────────────────────────

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1]

const cardVariants = {
  hidden:  { opacity: 0, y: 20, scale: 0.97 },
  visible: { opacity: 1, y: 0,  scale: 1, transition: { duration: 0.45, ease: EASE } },
}

const containerVariants = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.07, delayChildren: 0.04 } },
}

// Subject config — no hardcoded subject strings in render paths
const SUBJECT_CARDS = [
  { name: 'Physics'   as const, color: '#3b82f6', bgClass: 'bg-blue-50',    textClass: 'text-blue-600',    borderClass: 'border-blue-200'    },
  { name: 'Chemistry' as const, color: '#10b981', bgClass: 'bg-emerald-50', textClass: 'text-emerald-600', borderClass: 'border-emerald-200' },
  { name: 'Maths'     as const, color: '#8b5cf6', bgClass: 'bg-violet-50',  textClass: 'text-violet-600',  borderClass: 'border-violet-200'  },
]

const PREF_PREFIX = 'upmyrank_pref_'

// Preference definitions
const PREF_DEFS = [
  { key: 'show_hint_badges',    label: 'Show hint level badges',   defaultVal: true  },
  { key: 'show_confidence_meter', label: 'Show confidence meter',  defaultVal: true  },
  { key: 'compact_messages',    label: 'Compact message view',      defaultVal: false },
] as const

// ── Helpers ───────────────────────────────────────────────────────────────────

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/**
 * Derive subject mastery (0–100) by matching topic_mastery keys
 * against the static SYLLABUS_MAP topic names for that subject.
 */
function computeSubjectMastery(
  topicMastery: Record<string, { average: number }>,
  subject: 'Physics' | 'Chemistry' | 'Maths',
): number {
  const syllabusSubject = SYLLABUS_MAP[subject]
  if (!syllabusSubject) return 0

  // Build a set of all topic names (lowercase) for this subject
  const subjectTopics = new Set<string>()
  for (const chapter of syllabusSubject.chapters) {
    for (const topic of chapter.topics) {
      subjectTopics.add(topic.name.toLowerCase())
    }
    subjectTopics.add(chapter.name.toLowerCase())
  }

  const matches: number[] = []
  for (const [key, val] of Object.entries(topicMastery)) {
    if (subjectTopics.has(key.toLowerCase())) {
      matches.push(val.average)
    }
  }

  if (matches.length === 0) return 0
  const avg = matches.reduce((a, b) => a + b, 0) / matches.length
  return Math.round(avg * 100)
}

function masteryBarColor(mastery: number): string {
  if (mastery < 50) return '#EF4444'
  if (mastery < 75) return '#F59E0B'
  return '#22C55E'
}

function scoreColor(score: number): string {
  if (score >= 1.5) return '#22C55E'
  if (score >= 1.0) return '#F59E0B'
  return '#EF4444'
}

function adherenceColor(rate: number): string {
  if (rate >= 0.7) return '#22C55E'
  if (rate >= 0.5) return '#F59E0B'
  return '#EF4444'
}

function readPref(key: string, defaultVal: boolean): boolean {
  if (typeof window === 'undefined') return defaultVal
  try {
    const stored = localStorage.getItem(`${PREF_PREFIX}${key}`)
    if (stored === null) return defaultVal
    return stored === 'true'
  } catch {
    return defaultVal
  }
}

function writePref(key: string, val: boolean): void {
  try {
    localStorage.setItem(`${PREF_PREFIX}${key}`, String(val))
  } catch {
    // localStorage unavailable — silent
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TabButton({
  id, label, icon, active, onClick,
}: {
  id: TabId
  label: string
  icon: React.ReactNode
  active: boolean
  onClick: (id: TabId) => void
}) {
  return (
    <button
      onClick={() => onClick(id)}
      className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold transition-all duration-200 whitespace-nowrap active:scale-95 ${
        active
          ? 'bg-slate-900 text-white shadow-sm'
          : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

// iOS-style toggle
function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none active:scale-95 ${
        checked ? 'bg-indigo-500' : 'bg-slate-200'
      }`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform duration-200 ${
          checked ? 'translate-x-5' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

// Strength chip for subject strengths
function StrengthChip({
  subject, level,
}: {
  subject: 'Physics' | 'Chemistry' | 'Maths'
  level: string
}) {
  const cfg = SUBJECT_CARDS.find((s) => s.name === subject)
  if (!cfg) return null
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${cfg.bgClass} ${cfg.textClass} ${cfg.borderClass}`}
    >
      {subject} · <span className="capitalize">{level}</span>
    </span>
  )
}

// Stat mini-card
function MiniStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-2xl p-5 shadow-[0_4px_20px_rgb(0,0,0,0.04)] flex-1">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-2">{label}</p>
      <p className="text-3xl font-extrabold text-slate-900 tracking-tight tabular-nums">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  )
}

// Custom bar chart tooltip
function WeakTopicTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  const pct = payload[0].value
  return (
    <div className="bg-white border border-slate-100 rounded-xl px-3.5 py-2.5 text-xs shadow-[0_8px_30px_rgb(0,0,0,0.08)]">
      <div className="text-slate-500 mb-0.5 max-w-[160px] truncate">{label}</div>
      <div className="font-bold" style={{ color: masteryBarColor(pct) }}>{pct}% mastery</div>
    </div>
  )
}

// System analytics score tooltip
function ScoreTooltip({ active, payload, label }: {
  active?: boolean; payload?: { value: number }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  const score = payload[0].value
  return (
    <div className="bg-white border border-slate-100 rounded-xl px-3.5 py-2.5 text-xs shadow-[0_8px_30px_rgb(0,0,0,0.08)]">
      <div className="text-slate-500 mb-0.5 max-w-[160px] truncate">{label}</div>
      <div className="font-bold" style={{ color: scoreColor(score) }}>{score.toFixed(2)} / 2.0</div>
    </div>
  )
}

// ── Tab content components ────────────────────────────────────────────────────

function ProfileTab({ genome, loading, onRefresh }: {
  genome: StudentGenome | null
  loading: boolean
  onRefresh: () => void
}) {
  const router = useRouter()

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white/60 rounded-3xl animate-pulse h-24" />
        ))}
      </div>
    )
  }

  if (!genome) {
    return (
      <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-10 text-center text-sm text-slate-400 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
        Failed to load profile. Try refreshing.
      </div>
    )
  }

  const persona = genome.persona_profile as PersonaProfile | null | undefined
  const initials = getInitials(genome.name)
  const overallPct = Math.round(genome.overall_mastery * 100)
  const resolvedPct = genome.total_sessions > 0
    ? Math.round((genome.resolved_sessions / genome.total_sessions) * 100) : 0

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-5"
    >
      {/* Identity card */}
      <motion.div
        variants={cardVariants}
        className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-7 shadow-[0_8px_30px_rgb(0,0,0,0.04)] flex flex-col sm:flex-row items-center sm:items-start gap-6"
      >
        {/* Avatar */}
        <div className="flex-shrink-0 w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg">
          <span className="text-2xl font-bold text-white tracking-tight">{initials}</span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0 text-center sm:text-left">
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">{genome.name}</h2>
          <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 mt-2">
            {genome.exam_type && (
              <span className="px-2.5 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-xs font-semibold text-indigo-700">
                {genome.exam_type}
              </span>
            )}
            {genome.target_year && (
              <span className="px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-600">
                Target {genome.target_year}
              </span>
            )}
            {persona?.priority_subject && (
              <span className="px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-xs font-semibold text-amber-700 flex items-center gap-1">
                <Star className="h-3 w-3" />
                Focus: {persona.priority_subject}
              </span>
            )}
          </div>

          {/* Subject strengths */}
          {persona?.subject_strengths && (
            <div className="flex flex-wrap gap-2 mt-3 justify-center sm:justify-start">
              {SUBJECT_CARDS.map((s) => {
                const level = persona.subject_strengths?.[s.name]
                if (!level) return null
                return <StrengthChip key={s.name} subject={s.name} level={level} />
              })}
            </div>
          )}
        </div>
      </motion.div>

      {/* Persona summary */}
      {persona?.persona_summary && (
        <motion.div
          variants={cardVariants}
          className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
        >
          <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
            <Zap className="h-3.5 w-3.5 text-indigo-400" />
            Learning Persona
          </p>
          <p className="text-sm text-slate-700 leading-relaxed italic before:content-['\u201c'] after:content-['\u201d'] before:text-2xl after:text-2xl before:text-slate-200 after:text-slate-200 before:mr-1 after:ml-1">
            {persona.persona_summary}
          </p>
        </motion.div>
      )}

      {/* Stats row */}
      <motion.div variants={cardVariants} className="flex flex-col sm:flex-row gap-4">
        <MiniStat
          label="Total Sessions"
          value={String(genome.total_sessions)}
          sub="study sessions completed"
        />
        <MiniStat
          label="Overall Mastery"
          value={`${overallPct}%`}
          sub="across all concepts"
        />
        <MiniStat
          label="Resolved Rate"
          value={`${resolvedPct}%`}
          sub={`${genome.resolved_sessions} of ${genome.total_sessions} resolved`}
        />
      </motion.div>

      {/* Actions */}
      <motion.div variants={cardVariants} className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-semibold transition-all duration-200 active:scale-95 shadow-sm hover:shadow-md disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Profile
        </button>
        <button
          onClick={() => router.push('/onboarding')}
          className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-slate-300 bg-white/80 hover:bg-white text-slate-700 text-sm font-semibold transition-all duration-200 active:scale-95 hover:-translate-y-0.5 hover:shadow-sm"
        >
          Redo Onboarding
        </button>
      </motion.div>
    </motion.div>
  )
}

function AnalyticsTab({ genome, loading }: {
  genome: StudentGenome | null
  loading: boolean
}) {
  const radialData = useMemo(() => {
    if (!genome) return []
    return SUBJECT_CARDS.map((s) => ({
      name: s.name,
      mastery: computeSubjectMastery(genome.topic_mastery, s.name),
      fill: s.color,
    }))
  }, [genome])

  const weakestData = useMemo(() => {
    if (!genome) return []
    return genome.weakest_concepts.slice(0, 5).map((c) => ({
      name: c.subtopic.length > 20 ? c.subtopic.slice(0, 19) + '…' : c.subtopic,
      mastery: Math.round(c.mastery * 100),
    }))
  }, [genome])

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white/60 rounded-3xl animate-pulse h-32" />
        ))}
      </div>
    )
  }

  if (!genome) {
    return (
      <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-10 text-center text-sm text-slate-400">
        Failed to load analytics. Try refreshing.
      </div>
    )
  }

  const resolvedPct = genome.total_sessions > 0
    ? parseFloat(((genome.resolved_sessions / genome.total_sessions) * 100).toFixed(0))
    : 0

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-5"
    >
      {/* Subject Mastery — Radial bars */}
      <motion.div
        variants={cardVariants}
        className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
      >
        <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1 flex items-center gap-2">
          <Target className="h-3.5 w-3.5 text-indigo-400" />
          Subject Mastery
        </p>
        <p className="text-xs text-slate-400 mb-4">Derived from your knowledge genome across all topics</p>
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <div className="w-full sm:w-64 h-48 flex-shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                cx="50%"
                cy="50%"
                innerRadius="25%"
                outerRadius="85%"
                data={radialData}
                startAngle={90}
                endAngle={-270}
              >
                <RadialBar
                  dataKey="mastery"
                  cornerRadius={6}
                  background={{ fill: '#f1f5f9' }}
                  label={false}
                />
                <Legend
                  iconSize={10}
                  formatter={(value) => (
                    <span className="text-xs text-slate-600">{value}</span>
                  )}
                />
                <Tooltip
                  contentStyle={{
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    fontSize: 12,
                    color: '#1e293b',
                    boxShadow: '0 8px 30px rgba(0,0,0,0.08)',
                  }}
                  formatter={(v) => [`${v}%`, 'Mastery']}
                />
              </RadialBarChart>
            </ResponsiveContainer>
          </div>

          {/* Subject breakdown list */}
          <div className="flex-1 w-full space-y-4">
            {radialData.map((s) => (
              <div key={s.name}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-semibold text-slate-700">{s.name}</span>
                  <span
                    className="text-sm font-bold tabular-nums"
                    style={{ color: s.fill }}
                  >
                    {s.mastery}%
                  </span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${s.mastery}%`, backgroundColor: s.fill }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Weakest topics */}
      <motion.div
        variants={cardVariants}
        className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
      >
        <p className="text-xs font-medium text-slate-500 uppercase tracking-widest mb-1 flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
          Weakest Topics
        </p>
        <p className="text-xs text-slate-400 mb-5">Top 5 concepts needing the most attention</p>

        {weakestData.length === 0 ? (
          <div className="text-center py-6 text-sm text-slate-400">
            No concept data yet — ask your first doubt to start building your genome.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={weakestData.length * 44 + 20}>
            <BarChart
              data={weakestData}
              layout="vertical"
              margin={{ top: 4, right: 16, bottom: 4, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 100]}
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={110}
                tick={{ fill: '#64748b', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<WeakTopicTooltip />} cursor={{ fill: 'rgba(0,0,0,0.03)' }} />
              <Bar dataKey="mastery" radius={[0, 6, 6, 0]}>
                {weakestData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={masteryBarColor(entry.mastery)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </motion.div>

      {/* Session stats */}
      <motion.div variants={cardVariants} className="flex flex-col sm:flex-row gap-4">
        <MiniStat
          label="Total Sessions"
          value={String(genome.total_sessions)}
          sub="study sessions completed"
        />
        <MiniStat
          label="Resolved Rate"
          value={`${resolvedPct}%`}
          sub={`${genome.resolved_sessions} doubts resolved`}
        />
      </motion.div>
    </motion.div>
  )
}

function PreferencesTab() {
  const [prefs, setPrefs] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {}
    for (const p of PREF_DEFS) {
      init[p.key] = readPref(p.key, p.defaultVal)
    }
    return init
  })

  const handleToggle = (key: string, val: boolean) => {
    writePref(key, val)
    setPrefs((prev) => ({ ...prev, [key]: val }))
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-3"
    >
      <motion.div
        variants={cardVariants}
        className="bg-white/80 backdrop-blur-md border border-white/50 rounded-3xl overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
      >
        <div className="px-6 py-5 border-b border-slate-100">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-widest flex items-center gap-2">
            <SlidersHorizontal className="h-3.5 w-3.5 text-indigo-400" />
            Display Preferences
          </p>
          <p className="text-xs text-slate-400 mt-1">Stored locally in your browser. No account sync.</p>
        </div>
        <div className="divide-y divide-slate-100/80">
          {PREF_DEFS.map((p) => (
            <div key={p.key} className="px-6 py-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-slate-800">{p.label}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {p.key === 'show_hint_badges'      && 'Shows numbered badges on AI responses indicating hint depth used.'}
                  {p.key === 'show_confidence_meter' && 'Shows the confidence slider in the chat input area.'}
                  {p.key === 'compact_messages'      && 'Reduces padding between chat messages for a denser view.'}
                </p>
              </div>
              <Toggle
                checked={prefs[p.key] ?? p.defaultVal}
                onChange={(val) => handleToggle(p.key, val)}
              />
            </div>
          ))}
        </div>
      </motion.div>

      <motion.div
        variants={cardVariants}
        className="bg-slate-50/80 border border-slate-200/60 rounded-2xl px-5 py-4"
      >
        <p className="text-xs text-slate-400">
          Preferences are saved to <code className="text-slate-500 font-mono text-[11px]">localStorage</code> with the key prefix <code className="text-slate-500 font-mono text-[11px]">upmyrank_pref_</code>. Clearing browser data will reset them to defaults.
        </p>
      </motion.div>
    </motion.div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { studentId } = useAuth()
  const [genome, setGenome] = useState<StudentGenome | null>(null)
  const [genomeLoading, setGenomeLoading] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('profile')

  // Fetch genome on mount
  const fetchGenome = async () => {
    if (!studentId) return
    setGenomeLoading(true)
    try {
      const data = await apiGet(`/student/${studentId}`)
      setGenome(data)
    } catch (e) {
      console.error('Settings: genome fetch failed', e)
    } finally {
      setGenomeLoading(false)
    }
  }

  // Check admin status on mount
  const checkAdmin = async () => {
    try {
      const data = await apiGet('/admin/is_admin')
      setIsAdmin(data?.is_admin === true)
    } catch {
      setIsAdmin(false)
    }
  }

  useEffect(() => {
    fetchGenome()
    checkAdmin()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentId])

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab)
  }

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'profile',     label: 'Profile',      icon: <User className="h-4 w-4" />              },
    { id: 'analytics',   label: 'My Analytics', icon: <BarChart3 className="h-4 w-4" />         },
    { id: 'preferences', label: 'Preferences',  icon: <SlidersHorizontal className="h-4 w-4" /> },
  ]

  const visibleTabs = tabs

  return (
    <AuthGuard>
      <div className="flex h-[100dvh]">
        <Sidebar />

        <div className="md:ml-[296px] flex-1 flex flex-col overflow-hidden pt-14 md:pt-0">

          {/* Page header */}
          <div className="px-6 pt-6 pb-2 flex-shrink-0">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-indigo-400" />
              Settings
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-medium uppercase tracking-wide">
              Profile · Analytics · Preferences
            </p>
          </div>

          {/* Sticky tab bar */}
          <div className="sticky top-0 z-10 bg-white/90 backdrop-blur-sm border-b border-slate-100 px-6 py-3 flex-shrink-0">
            <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-hide">
              {visibleTabs.map((tab) => (
                <TabButton
                  key={tab.id}
                  id={tab.id}
                  label={tab.label}
                  icon={tab.icon}
                  active={activeTab === tab.id}
                  onClick={handleTabChange}
                />
              ))}
            </div>
          </div>

          {/* Tab content — scrollable */}
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-6 py-6 pb-12">
              <AnimatePresence mode="wait">
                {activeTab === 'profile' && (
                  <motion.div
                    key="profile"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.25, ease: EASE }}
                  >
                    <ProfileTab
                      genome={genome}
                      loading={genomeLoading}
                      onRefresh={fetchGenome}
                    />
                    {isAdmin && (
                      <div className="mt-4 p-4 bg-purple-50 border border-purple-100 rounded-2xl flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-purple-700">Admin Dashboard</p>
                          <p className="text-xs text-purple-400 mt-0.5">Full platform metrics, conversation quality, diagnostics</p>
                        </div>
                        <a href="/admin"
                          className="px-4 py-2 bg-purple-600 text-white text-xs font-semibold rounded-xl hover:bg-purple-700 transition-all active:scale-95 shadow-[0_4px_12px_rgba(124,58,237,0.3)]">
                          Open →
                        </a>
                      </div>
                    )}
                  </motion.div>
                )}

                {activeTab === 'analytics' && (
                  <motion.div
                    key="analytics"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.25, ease: EASE }}
                  >
                    <AnalyticsTab genome={genome} loading={genomeLoading} />
                  </motion.div>
                )}

                {activeTab === 'preferences' && (
                  <motion.div
                    key="preferences"
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.25, ease: EASE }}
                  >
                    <PreferencesTab />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

        </div>
      </div>
    </AuthGuard>
  )
}
