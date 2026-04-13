'use client'

/**
 * TopicTree — Subject → Chapter → Topic navigation sidebar.
 *
 * Data flow:
 *   1. Fetches /taxonomy (live from concepts table)
 *   2. Falls back to STATIC_SYLLABUS if a subject has 0 chapters in the API response
 *   3. Merges mastery from StudentGenome.topic_mastery (keyed by subtopic name)
 *
 * Per-topic actions:
 *   Doubt     → /doubt?subject=…&chapter=…&topic=…
 *   Practice  → /practice  (coming soon toast)
 *   Mock      → /mock      (coming soon toast)
 */

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronDown, ChevronRight,
  MessageCircle, Target, Timer, Loader2,
} from 'lucide-react'
import { apiGet } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import {
  STATIC_SYLLABUS, SYLLABUS_MAP,
  masteryColor, masteryBg,
  SyllabusChapter, SyllabusTopic,
} from '@/lib/syllabus'
import { StudentGenome } from '@/lib/types'

// ── Types mirroring /taxonomy response ────────────────────────────────────────

interface TaxonomyChapter { name: string; topics: string[] }
interface TaxonomySubject { name: string; chapters: TaxonomyChapter[] }
interface TaxonomyResponse { subjects: TaxonomySubject[] }

// ── Subject tab config ─────────────────────────────────────────────────────────

const SUBJECT_TABS = [
  { name: 'Physics',   short: 'Phy', color: 'text-blue-600',    activeBg: 'bg-blue-600'    },
  { name: 'Chemistry', short: 'Che', color: 'text-emerald-600', activeBg: 'bg-emerald-600' },
  { name: 'Maths',     short: 'Mat', color: 'text-violet-600',  activeBg: 'bg-violet-600'  },
] as const

type SubjectName = typeof SUBJECT_TABS[number]['name']

// ── Helper: merge API taxonomy with static fallback ────────────────────────────

function mergeSubject(
  subjectName: SubjectName,
  apiSubjects: TaxonomySubject[],
): SyllabusChapter[] {
  const apiSubject = apiSubjects.find((s) => s.name === subjectName)
  if (apiSubject && apiSubject.chapters.length > 0) {
    // Use live API data
    return apiSubject.chapters.map((ch) => ({
      id: `${subjectName}__${ch.name}`.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
      name: ch.name,
      topics: ch.topics.map((t) => ({
        id: `${subjectName}__${ch.name}__${t}`.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        name: t,
      })),
    }))
  }
  // Fallback to static constant
  return SYLLABUS_MAP[subjectName]?.chapters ?? []
}

// ── Mastery lookup ─────────────────────────────────────────────────────────────

function lookupMastery(
  topicName: string,
  topicMastery: Record<string, { average: number; concepts: unknown[] }>,
): number {
  // TODO: topic_mastery keys may not exactly match topic names from the syllabus.
  // Normalise both sides to lowercase for a best-effort match.
  const needle = topicName.toLowerCase()
  const entry = Object.entries(topicMastery).find(([k]) => k.toLowerCase() === needle)
  return entry ? entry[1].average : 0
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function TopicRow({
  topic,
  mastery,
  subject,
  chapter,
  onAction,
}: {
  topic: SyllabusTopic
  mastery: number
  subject: SubjectName
  chapter: string
  onAction: (action: 'doubt' | 'practice' | 'mock', topic: SyllabusTopic) => void
}) {
  const pct = Math.round(mastery * 100)
  const color = masteryColor(mastery)
  const barBg = masteryBg(mastery)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -4 }}
      transition={{ duration: 0.18 }}
      className="group flex flex-col gap-1.5 px-3 py-2 rounded-xl hover:bg-slate-50/80 transition-colors duration-150"
    >
      {/* Topic name + action buttons */}
      <div className="flex items-center gap-2 min-h-[36px]">
        <span className="flex-1 text-[13px] text-slate-700 font-medium leading-tight min-w-0 truncate">
          {topic.name}
        </span>

        {/* Action icon buttons — always visible on mobile, hover-reveal on desktop */}
        <div className="flex items-center gap-0.5 flex-shrink-0 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-150">
          <button
            onClick={(e) => { e.stopPropagation(); onAction('doubt', topic) }}
            title={`Ask a doubt on ${topic.name}`}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-indigo-500 hover:bg-indigo-50 active:scale-90 transition-all duration-150 min-w-[28px] min-h-[28px]"
          >
            <MessageCircle style={{ width: 13, height: 13 }} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onAction('practice', topic) }}
            title={`Practice ${topic.name}`}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-emerald-500 hover:bg-emerald-50 active:scale-90 transition-all duration-150 min-w-[28px] min-h-[28px]"
          >
            <Target style={{ width: 13, height: 13 }} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onAction('mock', topic) }}
            title={`Mock test: ${topic.name}`}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-amber-500 hover:bg-amber-50 active:scale-90 transition-all duration-150 min-w-[28px] min-h-[28px]"
          >
            <Timer style={{ width: 13, height: 13 }} />
          </button>
        </div>
      </div>

      {/* Mastery bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${barBg}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-[10px] font-semibold tabular-nums flex-shrink-0" style={{ color }}>
          {pct}%
        </span>
      </div>
    </motion.div>
  )
}

function ChapterAccordion({
  chapter,
  subject,
  topicMastery,
  isOpen,
  onToggle,
  onAction,
}: {
  chapter: SyllabusChapter
  subject: SubjectName
  topicMastery: Record<string, { average: number; concepts: unknown[] }>
  isOpen: boolean
  onToggle: () => void
  onAction: (action: 'doubt' | 'practice' | 'mock', topic: SyllabusTopic) => void
}) {
  // Chapter-level mastery = average of its topics
  const topicMasteries = chapter.topics.map((t) => lookupMastery(t.name, topicMastery))
  const chapterMastery = topicMasteries.length
    ? topicMasteries.reduce((a, b) => a + b, 0) / topicMasteries.length
    : 0
  const chPct = Math.round(chapterMastery * 100)
  const chColor = masteryColor(chapterMastery)
  const chBar = masteryBg(chapterMastery)

  return (
    <div className="rounded-xl overflow-hidden border border-slate-100/80">
      {/* Chapter header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left bg-white/60 hover:bg-slate-50 active:bg-slate-100 transition-colors duration-150 min-h-[44px]"
      >
        <span className="flex-shrink-0 text-slate-400">
          {isOpen
            ? <ChevronDown style={{ width: 13, height: 13 }} />
            : <ChevronRight style={{ width: 13, height: 13 }} />}
        </span>
        <span className="flex-1 text-[13px] font-semibold text-slate-800 leading-tight truncate">
          {chapter.name}
        </span>
        {/* Chapter mastery mini bar */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <div className="w-12 h-1 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${chBar}`}
              style={{ width: `${chPct}%` }}
            />
          </div>
          <span className="text-[10px] font-semibold tabular-nums w-7 text-right" style={{ color: chColor }}>
            {chPct}%
          </span>
        </div>
      </button>

      {/* Topics list */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="topics"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.25, 0.1, 0.25, 1] }}
            className="overflow-hidden bg-white/40"
          >
            <div className="px-1 py-1 space-y-0.5">
              {chapter.topics.map((topic) => (
                <TopicRow
                  key={topic.id}
                  topic={topic}
                  mastery={lookupMastery(topic.name, topicMastery)}
                  subject={subject}
                  chapter={chapter.name}
                  onAction={onAction}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function TopicTree({ onNavigate }: { onNavigate?: () => void }) {
  const router = useRouter()
  const { studentId } = useAuth()

  const [activeSubject, setActiveSubject] = useState<SubjectName>('Physics')
  const [apiSubjects,   setApiSubjects]   = useState<TaxonomySubject[]>([])
  const [topicMastery,  setTopicMastery]  = useState<Record<string, { average: number; concepts: unknown[] }>>({})
  const [loading,       setLoading]       = useState(true)
  // key = chapterId, open = expanded
  const [openChapters, setOpenChapters] = useState<Set<string>>(new Set())
  // Coming soon toast
  const [toast, setToast] = useState<string | null>(null)

  // ── Fetch taxonomy + mastery concurrently ──────────────────────────────────
  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const [taxonomyRes, genomeRes] = await Promise.allSettled([
          apiGet('/taxonomy'),
          studentId ? apiGet(`/student/${studentId}`) : Promise.reject('no id'),
        ])

        if (cancelled) return

        if (taxonomyRes.status === 'fulfilled') {
          const data = taxonomyRes.value as TaxonomyResponse
          setApiSubjects(data.subjects ?? [])
        }

        if (genomeRes.status === 'fulfilled') {
          const genome = genomeRes.value as StudentGenome
          setTopicMastery(genome.topic_mastery ?? {})
        }
      } catch {
        // non-fatal — tree renders with 0% mastery
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [studentId])

  // Auto-open first chapter of active subject on subject switch
  useEffect(() => {
    const chapters = mergeSubject(activeSubject, apiSubjects)
    if (chapters.length > 0) {
      setOpenChapters(new Set([chapters[0].id]))
    }
  }, [activeSubject, apiSubjects])

  const toggleChapter = useCallback((chapterId: string) => {
    setOpenChapters((prev) => {
      const next = new Set(prev)
      next.has(chapterId) ? next.delete(chapterId) : next.add(chapterId)
      return next
    })
  }, [])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }

  const handleAction = useCallback(
    (action: 'doubt' | 'practice' | 'mock', topic: SyllabusTopic) => {
      if (action === 'doubt') {
        // Find chapter name from topic id (slug contains subject__chapter__topic)
        const chapters = mergeSubject(activeSubject, apiSubjects)
        const parentChapter = chapters.find((ch) =>
          ch.topics.some((t) => t.id === topic.id),
        )
        const params = new URLSearchParams({
          subject: activeSubject,
          chapter: parentChapter?.name ?? '',
          topic:   topic.name,
        })
        router.push(`/doubt?${params.toString()}`)
        onNavigate?.()
      } else {
        // TODO: wire Practice and Mock to topic-scoped pages when built
        showToast(`${action === 'practice' ? 'Practice' : 'Mock test'} coming soon for "${topic.name}"`)
      }
    },
    [activeSubject, apiSubjects, router, onNavigate],
  )

  const chapters = mergeSubject(activeSubject, apiSubjects)

  return (
    <div className="flex flex-col h-full">
      {/* ── Subject tabs ────────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 px-3 pt-3 pb-2">
        <div className="flex gap-1 p-1 bg-slate-100/80 rounded-2xl">
          {SUBJECT_TABS.map((tab) => {
            const active = activeSubject === tab.name
            return (
              <button
                key={tab.name}
                onClick={() => setActiveSubject(tab.name as SubjectName)}
                className={`flex-1 py-2 rounded-xl text-[12px] font-semibold transition-all duration-200 min-h-[36px] ${
                  active
                    ? `${tab.activeBg} text-white shadow-sm`
                    : `${tab.color} hover:bg-white/60`
                }`}
              >
                {tab.short}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Chapter/topic list ───────────────────────────────────────────────── */}
      <div
        className="flex-1 overflow-y-auto px-2 pb-4 space-y-1"
        style={{ WebkitOverflowScrolling: 'touch' } as React.CSSProperties}
      >
        {loading ? (
          <div className="flex items-center justify-center py-10 gap-2 text-slate-400 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading syllabus…
          </div>
        ) : chapters.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400">
            No chapters found for {activeSubject}
          </div>
        ) : (
          chapters.map((chapter) => (
            <ChapterAccordion
              key={chapter.id}
              chapter={chapter}
              subject={activeSubject}
              topicMastery={topicMastery}
              isOpen={openChapters.has(chapter.id)}
              onToggle={() => toggleChapter(chapter.id)}
              onAction={handleAction}
            />
          ))
        )}
      </div>

      {/* ── Coming soon toast ────────────────────────────────────────────────── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.96 }}
            transition={{ duration: 0.2 }}
            className="absolute bottom-4 left-3 right-3 bg-slate-800/90 backdrop-blur-sm text-white text-xs font-medium rounded-2xl px-4 py-2.5 shadow-lg text-center pointer-events-none z-50"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
