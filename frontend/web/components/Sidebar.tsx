'use client'

import { useState, useCallback, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageCircle, Target, Timer, BarChart3,
  LayoutDashboard, Settings, RefreshCw,
  Flame, BookOpen, CheckCircle, X, Menu, Brain,
  LogOut, ChevronRight,
} from 'lucide-react'
import { apiGet } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { StudentGenome } from '@/lib/types'

const SCAFFOLDING_BADGE: Record<string, { label: string; cls: string }> = {
  HIGH:   { label: 'Beginner',     cls: 'bg-amber-50 border-amber-200 text-amber-700'      },
  MEDIUM: { label: 'Intermediate', cls: 'bg-blue-50 border-blue-200 text-blue-700'         },
  LOW:    { label: 'Advanced',     cls: 'bg-emerald-50 border-emerald-200 text-emerald-700' },
}
const STYLE_ICON: Record<string, string> = {
  analogy: '💡', formula: '📐', example: '🔍', visual: '🎨',
}

const NAV_ITEMS = [
  { label: 'Dashboard',   icon: LayoutDashboard, href: '/'         },
  { label: 'Ask a doubt', icon: MessageCircle,   href: '/doubt'    },
  { label: 'Practice',    icon: Target,          href: '/practice' },
  { label: 'Mock test',   icon: Timer,           href: '/mock'     },
  { label: 'Analytics',   icon: BarChart3,       href: '/progress' },
]

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export default function Sidebar() {
  const pathname = usePathname()
  const router   = useRouter()
  const { studentId, logout } = useAuth()
  const [genome,     setGenome]     = useState<StudentGenome | null>(null)
  const [loading,    setLoading]    = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  const fetchGenome = useCallback(async () => {
    if (!studentId) return
    setLoading(true)
    try {
      setGenome(await apiGet(`/student/${studentId}`))
    } catch (e) {
      console.error('Sidebar: failed to fetch genome', e)
    } finally {
      setLoading(false)
    }
  }, [studentId])

  useEffect(() => { fetchGenome() }, [fetchGenome])
  useEffect(() => { setMobileOpen(false) }, [pathname])

  const initials = genome?.name ? getInitials(genome.name) : '…'

  const handleLogout = () => {
    logout()
    router.push('/auth/login')
  }

  // ── Desktop expanded sidebar ───────────────────────────────────────────────
  const desktopNav = (
    <div className="flex flex-col h-full py-5">
      {/* ── Student identity ──────────────────────────────────────────────── */}
      <div className="px-4 mb-5 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-xs font-bold text-white select-none shadow-md flex-shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-slate-800 truncate leading-tight">
              {genome?.name ?? 'Loading…'}
            </div>
            <div className="text-[11px] text-slate-500 truncate">
              {genome?.exam_type ?? 'JEE'} · {genome?.target_year ?? '—'}
            </div>
          </div>
        </div>

        {/* Quick stats row */}
        {genome && (
          <div className="flex gap-2 mt-3">
            <div className="flex-1 rounded-xl bg-slate-50 border border-slate-100 px-2.5 py-1.5 text-center">
              <div className="text-sm font-bold text-slate-800">{genome.total_sessions}</div>
              <div className="text-[10px] text-slate-400 font-medium">Sessions</div>
            </div>
            <div className="flex-1 rounded-xl bg-slate-50 border border-slate-100 px-2.5 py-1.5 text-center">
              <div className="text-sm font-bold text-emerald-600">
                {Math.round(genome.overall_mastery * 100)}%
              </div>
              <div className="text-[10px] text-slate-400 font-medium">Mastery</div>
            </div>
            <div className="flex-1 rounded-xl bg-slate-50 border border-slate-100 px-2.5 py-1.5 text-center">
              <div className="text-sm font-bold text-slate-800">{genome.resolved_sessions}</div>
              <div className="text-[10px] text-slate-400 font-medium">Solved</div>
            </div>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="mx-4 mb-3 border-t border-slate-100 flex-shrink-0" />

      {/* ── Nav items ─────────────────────────────────────────────────────── */}
      <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ label, icon: Icon, href }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`group flex items-center gap-3 px-3 py-2.5 rounded-2xl text-sm font-medium transition-all duration-150 ${
                active
                  ? 'bg-slate-900 text-white shadow-sm shadow-slate-900/20'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100/80'
              }`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" style={{ width: 16, height: 16 }} />
              <span className="flex-1">{label}</span>
              {active && (
                <ChevronRight className="h-3 w-3 opacity-50" style={{ width: 12, height: 12 }} />
              )}
            </Link>
          )
        })}
      </nav>

      {/* ── Learning profile (if persona exists) ──────────────────────────── */}
      {genome?.persona_profile && (() => {
        const p = genome.persona_profile!
        const badge = SCAFFOLDING_BADGE[p.scaffolding_level] ?? { label: p.scaffolding_level, cls: 'bg-slate-100 border-slate-200 text-slate-600' }
        const styleIcon = STYLE_ICON[p.preferred_style] ?? '📚'
        const weakConcepts = (p.weak_concepts ?? []).slice(0, 2)
        return (
          <div className="flex-shrink-0 mx-3 mt-3 rounded-2xl bg-slate-50 border border-slate-100 px-3 py-3">
            <div className="flex items-center gap-1.5 mb-2.5">
              <Brain className="h-3 w-3 text-slate-400" style={{ width: 12, height: 12 }} />
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Learning Profile</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold ${badge.cls}`}>
                {badge.label}
              </span>
              <span className="text-[11px] text-slate-500">{styleIcon} {p.preferred_style}</span>
            </div>
            {weakConcepts.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {weakConcepts.map((c) => (
                  <span key={c} className="px-2 py-0.5 rounded-full bg-rose-50 border border-rose-100 text-[10px] text-rose-600 font-medium">
                    {c.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}
          </div>
        )
      })()}

      {/* Divider */}
      <div className="mx-4 my-3 border-t border-slate-100 flex-shrink-0" />

      {/* ── Bottom actions ─────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 px-3 space-y-0.5">
        <button
          onClick={fetchGenome}
          disabled={loading}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-2xl text-sm font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100/80 transition-all duration-150 disabled:opacity-40"
        >
          <RefreshCw className={`h-4 w-4 flex-shrink-0 ${loading ? 'animate-spin' : ''}`} style={{ width: 16, height: 16 }} />
          <span>Refresh data</span>
        </button>
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-2xl text-sm font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100/80 transition-all duration-150"
        >
          <Settings className="h-4 w-4 flex-shrink-0" style={{ width: 16, height: 16 }} />
          <span>Settings</span>
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-2xl text-sm font-medium text-rose-500 hover:text-rose-700 hover:bg-rose-50 transition-all duration-150"
        >
          <LogOut className="h-4 w-4 flex-shrink-0" style={{ width: 16, height: 16 }} />
          <span>Log out</span>
        </button>
      </div>
    </div>
  )

  // ── Mobile full panel (unchanged) ──────────────────────────────────────────
  const mobilePanel = (
    <div className="flex flex-col h-full bg-white/90 backdrop-blur-xl">
      <div className="px-4 pt-6 pb-4 border-b border-slate-100 flex-shrink-0">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center flex-shrink-0 text-xs font-bold text-white">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-slate-800 truncate">
              {genome?.name ?? 'Loading…'}
            </div>
            <div className="text-xs text-slate-500">
              {genome?.exam_type ?? 'JEE'} · {genome?.target_year ?? '—'}
            </div>
          </div>
        </div>
        {genome && (
          <div className="flex flex-wrap gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] bg-amber-50 border border-amber-200 text-amber-700">
              <Flame className="h-3 w-3" /> <span className="font-semibold">1d</span> <span className="opacity-70">streak</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] bg-slate-100 border border-slate-200 text-slate-600">
              <BookOpen className="h-3 w-3" /> <span className="font-semibold">{genome.total_sessions}</span> <span className="opacity-70">sessions</span>
            </span>
            <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] bg-slate-100 border border-slate-200 text-slate-600">
              <CheckCircle className="h-3 w-3" /> <span className="font-semibold">{genome.resolved_sessions}</span> <span className="opacity-70">resolved</span>
            </span>
          </div>
        )}
      </div>
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ label, icon: Icon, href }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                active
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
              }`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      {genome?.persona_profile && (() => {
        const p = genome.persona_profile!
        const badge = SCAFFOLDING_BADGE[p.scaffolding_level] ?? { label: p.scaffolding_level, cls: 'bg-slate-100 border-slate-200 text-slate-600' }
        const styleIcon = STYLE_ICON[p.preferred_style] ?? '📚'
        const weakConcepts = (p.weak_concepts ?? []).slice(0, 2)
        return (
          <div className="flex-shrink-0 border-t border-slate-100 px-4 py-4">
            <div className="flex items-center gap-1.5 mb-3">
              <Brain className="h-3 w-3 text-slate-400" />
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Learning Profile</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded-full border text-[11px] font-semibold ${badge.cls}`}>
                {badge.label}
              </span>
              <span className="text-xs text-slate-500">{styleIcon} {p.preferred_style}</span>
            </div>
            {weakConcepts.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {weakConcepts.map((c) => (
                  <span key={c} className="px-2 py-0.5 rounded-full bg-rose-50 border border-rose-100 text-[10px] text-rose-600 font-medium">
                    {c.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}
          </div>
        )
      })()}

      <div className="flex-shrink-0 border-t border-slate-100 px-3 py-4 space-y-0.5">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-all"
        >
          <Settings className="h-4 w-4 flex-shrink-0" />
          Settings
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-rose-500 hover:text-rose-700 hover:bg-rose-50 transition-all"
        >
          <LogOut className="h-4 w-4 flex-shrink-0" />
          Log out
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* ── Desktop expanded sidebar (220px) ─────────────────────────────── */}
      <aside className="hidden md:flex fixed left-0 top-0 h-full w-[220px] z-40 flex-col">
        <div className="m-3 flex-1 w-full rounded-3xl bg-white/75 backdrop-blur-xl border border-white/60 shadow-xl shadow-slate-200/50 overflow-hidden">
          {desktopNav}
        </div>
      </aside>

      {/* ── Mobile bottom nav ─────────────────────────────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 h-14 bg-white/80 backdrop-blur-xl border-t border-slate-200/60 flex items-center justify-around px-1">
        {NAV_ITEMS.map(({ icon: Icon, href, label }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex flex-col items-center justify-center gap-0.5 min-w-[52px] min-h-[44px] px-2 rounded-xl transition-colors ${
                active ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className="text-[10px] font-medium leading-tight">
                {label.split(' ')[0]}
              </span>
            </Link>
          )
        })}
        <button
          onClick={() => setMobileOpen(true)}
          className={`flex flex-col items-center justify-center gap-0.5 min-w-[52px] min-h-[44px] px-2 rounded-xl transition-colors ${
            mobileOpen ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600'
          }`}
        >
          <Menu className="h-5 w-5" />
          <span className="text-[10px] font-medium leading-tight">Menu</span>
        </button>
      </nav>

      {/* ── Mobile slide-over ─────────────────────────────────────────────── */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            key="mobile-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden fixed inset-0 z-[60]"
          >
            <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
            <motion.div
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
              className="absolute left-0 top-0 h-full w-[280px] max-w-[85vw] z-10 shadow-2xl"
            >
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute top-4 right-3 z-20 w-7 h-7 flex items-center justify-center rounded-full bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
              {mobilePanel}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
