'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ChevronDown, ChevronRight, BookOpen, Loader2 } from 'lucide-react'
import { apiGet } from '@/lib/api'

interface Chapter {
  name: string
  topics: string[]
}

interface Subject {
  name: string
  chapters: Chapter[]
}

interface TaxonomyResponse {
  subjects: Subject[]
}

export default function SyllabusSelector() {
  const router = useRouter()
  const [data, setData] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Track which chapters are expanded: key = "subjectName::chapterName"
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    apiGet('/taxonomy')
      .then((res: TaxonomyResponse) => {
        setData(res.subjects ?? [])
        // Auto-expand the first chapter of the first subject
        if (res.subjects?.[0]?.chapters?.[0]) {
          const first = `${res.subjects[0].name}::${res.subjects[0].chapters[0].name}`
          setExpanded(new Set([first]))
        }
      })
      .catch((e) => setError(e.message ?? 'Failed to load syllabus'))
      .finally(() => setLoading(false))
  }, [])

  const toggleChapter = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const handleTopicClick = (topic: string) => {
    router.push(`/doubt?topic=${encodeURIComponent(topic)}`)
  }

  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-2xl p-6 shadow-sm flex items-center gap-3 text-slate-400 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading syllabus…
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-2xl p-6 shadow-sm text-sm text-red-500">
        Could not load syllabus. {error}
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-2xl p-6 shadow-sm text-sm text-slate-400">
        No syllabus data found. Ingest some NCERT content first.
      </div>
    )
  }

  return (
    <div className="bg-white/80 backdrop-blur-md border border-white/50 rounded-2xl p-6 shadow-sm space-y-6">
      <div className="flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-indigo-500" />
        <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider">Syllabus</h2>
        <span className="text-xs text-slate-400 font-normal ml-1">— click a topic to start a locked session</span>
      </div>

      {data.map((subject) => (
        <div key={subject.name}>
          {/* Subject heading */}
          <p className="text-xs font-bold text-indigo-600 uppercase tracking-widest mb-3">
            {subject.name}
          </p>

          {/* Chapters accordion */}
          <div className="space-y-1.5">
            {subject.chapters.map((chapter) => {
              const key = `${subject.name}::${chapter.name}`
              const isOpen = expanded.has(key)
              return (
                <div key={chapter.name} className="rounded-xl border border-slate-100 overflow-hidden">
                  {/* Chapter header — toggle */}
                  <button
                    onClick={() => toggleChapter(key)}
                    className="w-full flex items-center justify-between px-4 py-3 text-left bg-slate-50/80 hover:bg-slate-100/80 transition-colors"
                  >
                    <span className="text-sm font-semibold text-slate-800">{chapter.name}</span>
                    <span className="text-slate-400 flex-shrink-0 ml-2">
                      {isOpen
                        ? <ChevronDown className="h-4 w-4" />
                        : <ChevronRight className="h-4 w-4" />}
                    </span>
                  </button>

                  {/* Topics — shown when expanded */}
                  {isOpen && (
                    <div className="px-4 py-3 flex flex-wrap gap-2 bg-white/60">
                      {chapter.topics.map((topic) => (
                        <button
                          key={topic}
                          onClick={() => handleTopicClick(topic)}
                          className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-100 rounded-full px-4 py-1.5 text-sm font-medium transition-colors"
                        >
                          {topic}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
