'use client'

/**
 * Concept Card — v0.20 dual-loop Mode 1.
 *
 * Fetches GET /study/card?subject=&chapter=&topic= and renders four sections:
 *   1. Notes    — top-3 NCERT chunks (no LLM)
 *   2. Practice — up to 3 problems from the `problems` table
 *   3. PYQs     — JEE past-year questions filtered by topic
 *   4. Ask      — deep link to /doubt with topic-lock
 *
 * Topic mastery bar is rendered at the top using the student genome.
 */

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft, BookOpen, Target, Trophy, MessageCircle, Loader2,
  BookMarked, ChevronRight,
} from 'lucide-react'

import AppShell from '@/components/AppShell'
import AuthGuard from '@/components/AuthGuard'
import MathText from '@/components/MathText'
import { apiGet } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface ConceptCardResponse {
  subject: string
  chapter: string | null
  topic: string
  notes:    { chunks: Array<{ heading: string; text: string; source: string; similarity: number }>; error?: string }
  practice: { problems: Array<{ problem_id: string; question_text: string; question_latex: string; topic: string; subtopic: string; difficulty: number }>; error?: string }
  pyqs:     { problems: Array<{ problem_id: string; subject: string; topic: string; year: number | null; exam_type: string; difficulty: number; problem_text: string; verified: boolean }> }
  mastery:  { current: number | null; last_reviewed: string | null; attempts: number }
}

export default function ConceptCardPage() {
  const params = useParams<{ subject: string; chapter: string; topic: string }>()
  const router = useRouter()

  const subject = decodeURIComponent(params.subject)
  const chapter = decodeURIComponent(params.chapter)
  const topic   = decodeURIComponent(params.topic)

  const [card, setCard] = useState<ConceptCardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    const q = new URLSearchParams({ subject, chapter, topic }).toString()
    apiGet(`/study/card?${q}`)
      .then((d: ConceptCardResponse) => setCard(d))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [subject, chapter, topic])

  const masteryPct = card?.mastery?.current != null
    ? Math.round(card.mastery.current * 100)
    : null

  return (
    <AuthGuard>
      <AppShell maxWidth="max-w-4xl">
        <div className="space-y-6">

          {/* Breadcrumb + header */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <button
                onClick={() => router.back()}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mb-2"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back
              </button>
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                <Badge variant="outline">{subject}</Badge>
                <span>·</span>
                <span className="truncate">{chapter}</span>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">{topic}</h1>
            </div>
            {masteryPct != null && (
              <div className="shrink-0 rounded-xl border border-border bg-card px-4 py-2 text-right">
                <div className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">Mastery</div>
                <div className="text-2xl font-bold text-foreground tabular-nums">{masteryPct}%</div>
                <Progress value={masteryPct} className="mt-1 h-1 w-20" />
              </div>
            )}
          </div>

          {error && (
            <Card className="border-destructive/30 bg-destructive/5">
              <CardContent className="pt-6 text-sm text-destructive">
                Failed to load concept card: {error}
              </CardContent>
            </Card>
          )}

          {loading && !card && (
            <div className="space-y-4">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          )}

          {card && (
            <>
              {/* Notes */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-primary" />
                    <CardTitle>Notes</CardTitle>
                  </div>
                  <CardDescription>
                    Assembled from the indexed NCERT corpus. Review, then try the practice problems below.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {card.notes.chunks.length === 0 ? (
                    <EmptyFallback
                      label="Notes for this topic are still being indexed."
                      ctaHref={askDeepLink(subject, chapter, topic)}
                      ctaLabel="Ask the tutor instead"
                    />
                  ) : (
                    card.notes.chunks.map((chunk, i) => (
                      <div key={i} className="border-l-2 border-border pl-4">
                        <div className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground mb-1">
                          {chunk.heading}
                        </div>
                        <div className="prose prose-sm max-w-none text-sm leading-relaxed text-foreground/90">
                          <MathText>{chunk.text}</MathText>
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-1.5">
                          Source: {chunk.source}
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              {/* Practice */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Target className="h-4 w-4 text-emerald-600" />
                    <CardTitle>Practice</CardTitle>
                  </div>
                  <CardDescription>Warm-up problems scoped to this topic. Tap to solve Socratically.</CardDescription>
                </CardHeader>
                <CardContent>
                  {card.practice.problems.length === 0 ? (
                    <EmptyFallback
                      label="No practice problems for this topic yet."
                      ctaHref={askDeepLink(subject, chapter, topic)}
                      ctaLabel="Generate one via chat"
                    />
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {card.practice.problems.map((p) => (
                        <Link
                          key={p.problem_id}
                          href={askDeepLink(subject, chapter, topic, p.question_text)}
                          className="block rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40"
                        >
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
                              {p.subtopic || p.topic}
                            </span>
                            <Badge variant="outline" className="text-[10px]">
                              {difficultyLabel(p.difficulty)}
                            </Badge>
                          </div>
                          <div className="text-sm text-foreground line-clamp-3">
                            <MathText>{p.question_text}</MathText>
                          </div>
                          <div className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-primary">
                            Solve with tutor <ChevronRight className="h-3 w-3" />
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* PYQs */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Trophy className="h-4 w-4 text-amber-600" />
                    <CardTitle>Past-year questions</CardTitle>
                  </div>
                  <CardDescription>JEE problems from the last 5+ years that touch this topic.</CardDescription>
                </CardHeader>
                <CardContent>
                  {card.pyqs.problems.length === 0 ? (
                    <div className="text-sm text-muted-foreground">
                      No PYQs indexed for this topic yet. More coming soon.
                    </div>
                  ) : (
                    <ul className="space-y-2">
                      {card.pyqs.problems.map((q) => (
                        <li key={q.problem_id} className="flex items-start gap-3 rounded-lg border border-border p-3">
                          <BookMarked className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              {q.year && <Badge variant="secondary" className="text-[10px]">{q.exam_type || 'JEE'} {q.year}</Badge>}
                              {q.verified && <Badge variant="success" className="text-[10px]">Verified</Badge>}
                            </div>
                            <div className="text-sm text-foreground line-clamp-2">
                              <MathText>{q.problem_text}</MathText>
                            </div>
                          </div>
                          <Link
                            href={askDeepLink(subject, chapter, topic, q.problem_text)}
                            className="text-[11px] font-semibold text-primary whitespace-nowrap hover:underline"
                          >
                            Solve
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>

              {/* Ask about this topic */}
              <Card className="border-primary/20 bg-primary/5">
                <CardContent className="pt-6 flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                    <MessageCircle className="h-5 w-5 text-primary" />
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-foreground">Stuck somewhere specific?</div>
                    <div className="text-xs text-muted-foreground">Open a topic-locked chat — I&apos;ll guide you Socratically.</div>
                  </div>
                  <Button asChild>
                    <Link href={askDeepLink(subject, chapter, topic)}>
                      Ask about {topic}
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </AppShell>
    </AuthGuard>
  )
}

// ── helpers ───────────────────────────────────────────────────────────────

function askDeepLink(subject: string, chapter: string, topic: string, prompt?: string): string {
  const params = new URLSearchParams({ subject, chapter, topic })
  if (prompt) params.set('q', prompt.slice(0, 280))
  return `/doubt?${params.toString()}`
}

function difficultyLabel(d: number): string {
  if (d == null) return '—'
  if (d < 0.35) return 'Easy'
  if (d < 0.7)  return 'Medium'
  return 'Hard'
}

function EmptyFallback({ label, ctaHref, ctaLabel }: { label: string; ctaHref: string; ctaLabel: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-4 py-6">
      <span className="text-sm text-muted-foreground">{label}</span>
      <Button asChild size="sm" variant="outline">
        <Link href={ctaHref}>
          {ctaLabel}
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </Button>
    </div>
  )
}
