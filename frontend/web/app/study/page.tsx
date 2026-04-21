'use client'

/**
 * Study Path navigator — v0.20 dual-loop Mode 1.
 *
 * Subject → Chapter → Topic tree. Clicking a topic routes to the Concept Card
 * page at /study/[subject]/[chapter]/[topic]. No chat here; this is pure
 * navigation.
 */

import { useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import {
  BookOpen, ChevronRight, ChevronDown, Atom, FlaskConical, Calculator,
} from 'lucide-react'

import AppShell from '@/components/AppShell'
import AuthGuard from '@/components/AuthGuard'
import { SYLLABUS_MAP, SyllabusSubject } from '@/lib/syllabus'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const SUBJECT_META: Record<string, { icon: React.ComponentType<{ className?: string }>; accent: string; bg: string }> = {
  Physics:   { icon: Atom,         accent: 'text-blue-600',    bg: 'bg-blue-50' },
  Chemistry: { icon: FlaskConical, accent: 'text-emerald-600', bg: 'bg-emerald-50' },
  Maths:     { icon: Calculator,   accent: 'text-violet-600',  bg: 'bg-violet-50' },
}

function urlSegment(s: string): string {
  return encodeURIComponent(s)
}

export default function StudyPathPage() {
  return (
    <AuthGuard>
      <AppShell maxWidth="max-w-5xl">
        <div className="space-y-6">
          <header className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <BookOpen className="h-5 w-5 text-primary" />
                <h1 className="text-2xl font-bold tracking-tight text-foreground">Study Path</h1>
              </div>
              <p className="text-sm text-muted-foreground max-w-xl">
                Pick a topic to open its Concept Card — notes, practice problems, and past-year questions in one place.
              </p>
            </div>
            <Badge variant="secondary">Structured</Badge>
          </header>

          <div className="space-y-6">
            {Object.values(SYLLABUS_MAP).map((subject) => (
              <SubjectSection key={subject.name} subject={subject} />
            ))}
          </div>
        </div>
      </AppShell>
    </AuthGuard>
  )
}

function SubjectSection({ subject }: { subject: SyllabusSubject }) {
  const meta = SUBJECT_META[subject.name]
  const Icon = meta.icon

  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <div className={cn('flex h-8 w-8 items-center justify-center rounded-xl', meta.bg)}>
          <Icon className={cn('h-4 w-4', meta.accent)} />
        </div>
        <h2 className="text-base font-semibold text-foreground">{subject.name}</h2>
        <span className="text-xs text-muted-foreground">
          {subject.chapters.length} chapters · {subject.chapters.reduce((n, c) => n + c.topics.length, 0)} topics
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {subject.chapters.map((chapter) => (
          <ChapterCard
            key={chapter.id}
            subject={subject.name}
            chapterName={chapter.name}
            topics={chapter.topics}
            accent={meta.accent}
          />
        ))}
      </div>
    </section>
  )
}

function ChapterCard({
  subject, chapterName, topics, accent,
}: {
  subject: string
  chapterName: string
  topics: { id: string; name: string }[]
  accent: string
}) {
  const [open, setOpen] = useState(false)

  return (
    <Card className="p-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="text-sm font-semibold text-foreground truncate">{chapterName}</span>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          {topics.length}
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </span>
      </button>

      {open && (
        <motion.ul
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="mt-2 space-y-0.5 border-t border-border pt-2"
        >
          {topics.map((t) => (
            <li key={t.id}>
              <Link
                href={`/study/${urlSegment(subject)}/${urlSegment(chapterName)}/${urlSegment(t.name)}`}
                className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <span className="truncate">{t.name}</span>
                <ChevronRight className={cn('h-3.5 w-3.5 opacity-0 group-hover:opacity-100', accent)} />
              </Link>
            </li>
          ))}
        </motion.ul>
      )}
    </Card>
  )
}
