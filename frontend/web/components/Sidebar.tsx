'use client'

/**
 * Sidebar — Topic-tree navigation for UpMyRank.
 *
 * Desktop (md+):
 *   Fixed 220px left sidebar. Top: student identity card. Body: TopicTree.
 *   Bottom: nav links (Dashboard, Progress, Settings, Logout).
 *
 * Mobile (<md):
 *   Hidden by default.
 *   Top header bar (56px): hamburger left, logo center, avatar right.
 *   Hamburger → full-height left drawer containing TopicTree.
 *   Backdrop tap or swipe-left closes the drawer.
 */

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Menu, X, LayoutDashboard, BarChart3,
  Settings, LogOut, RefreshCw, Brain,
} from 'lucide-react'
import { apiGet } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { StudentGenome } from '@/lib/types'
import TopicTree from '@/components/TopicTree'

// ── Helpers ────────────────────────────────────────────────────────────────────

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

const SCAFFOLDING_BADGE: Record<string, { label: string; cls: string }> = {
  HIGH:   { label: 'Beginner',     cls: 'bg-amber-50 border-amber-200 text-amber-700'      },
  MEDIUM: { label: 'Intermediate', cls: 'bg-blue-50 border-blue-200 text-blue-700'         },
  LOW:    { label: 'Advanced',     cls: 'bg-emerald-50 border-emerald-200 text-emerald-700' },
}

// Bottom nav links shown in desktop sidebar footer + mobile drawer footer
const BOTTOM_LINKS = [
  { label: 'Dashboard', icon: LayoutDashboard, href: '/'         },
  { label: 'Progress',  icon: BarChart3,       href: '/progress' },
]

// ── Student identity card (shared desktop + mobile) ───────────────────────────

function IdentityCard({ genome, loading, onRefresh }: {
  genome: StudentGenome | null
  loading: boolean
  onRefresh: () => void
}) {
  const initials = genome?.name ? getInitials(genome.name) : '…'
  return (
    <div className="px-4 py-4 flex-shrink-0">
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
        <button
          onClick={onRefresh}
          disabled={loading}
          title="Refresh"
          className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-30"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Quick stats */}
      {genome && (
        <div className="flex gap-2 mt-3">
          <div className="flex-1 rounded-xl bg-slate-50 border border-slate-100 px-2 py-1.5 text-center">
            <div className="text-xs font-bold text-slate-800">{genome.total_sessions}</div>
            <div className="text-[10px] text-slate-400 font-medium">Sessions</div>
          </div>
          <div className="flex-1 rounded-xl bg-slate-50 border border-slate-100 px-2 py-1.5 text-center">
            <div className="text-xs font-bold text-emerald-600">
              {Math.round(genome.overall_mastery * 100)}%
            </div>
            <div className="text-[10px] text-slate-400 font-medium">Mastery</div>
          </div>
          <div className="flex-1 rounded-xl bg-slate-50 border border-slate-100 px-2 py-1.5 text-center">
            <div className="text-xs font-bold text-slate-800">{genome.resolved_sessions}</div>
            <div className="text-[10px] text-slate-400 font-medium">Solved</div>
          </div>
        </div>
      )}

      {/* Persona badge */}
      {genome?.persona_profile && (() => {
        const p = genome.persona_profile!
        const badge = SCAFFOLDING_BADGE[p.scaffolding_level] ?? { label: p.scaffolding_level, cls: 'bg-slate-100 border-slate-200 text-slate-600' }
        return (
          <div className="flex items-center gap-2 mt-2.5">
            <Brain className="h-3 w-3 text-slate-400 flex-shrink-0" />
            <span className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold ${badge.cls}`}>
              {badge.label}
            </span>
            <span className="text-[10px] text-slate-400 truncate">{p.preferred_style}</span>
          </div>
        )
      })()}
    </div>
  )
}

// ── Sidebar inner content (shared between desktop sidebar + mobile drawer) ─────

function SidebarContent({
  genome, loading, onRefresh, onNavigate,
}: {
  genome: StudentGenome | null
  loading: boolean
  onRefresh: () => void
  onNavigate: () => void
}) {
  const pathname = usePathname()
  const router   = useRouter()
  const { logout } = useAuth()

  const handleLogout = () => {
    logout()
    router.push('/auth/login')
  }

  return (
    <div className="flex flex-col h-full">
      {/* Identity */}
      <IdentityCard genome={genome} loading={loading} onRefresh={onRefresh} />

      {/* Divider */}
      <div className="mx-4 border-t border-slate-100 flex-shrink-0" />

      {/* Topic tree — fills remaining height */}
      <div className="flex-1 min-h-0 relative">
        <TopicTree onNavigate={onNavigate} />
      </div>

      {/* Divider */}
      <div className="mx-4 border-t border-slate-100 flex-shrink-0" />

      {/* Footer links */}
      <div className="flex-shrink-0 px-3 py-3 space-y-0.5">
        {BOTTOM_LINKS.map(({ label, icon: Icon, href }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 min-h-[44px] ${
                active
                  ? 'bg-slate-900 text-white'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100/80'
              }`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" style={{ width: 16, height: 16 }} />
              {label}
            </Link>
          )
        })}
        <Link
          href="/settings"
          onClick={onNavigate}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100/80 transition-all duration-150 min-h-[44px]"
        >
          <Settings className="h-4 w-4 flex-shrink-0" style={{ width: 16, height: 16 }} />
          Settings
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-rose-500 hover:text-rose-700 hover:bg-rose-50 transition-all duration-150 min-h-[44px]"
        >
          <LogOut className="h-4 w-4 flex-shrink-0" style={{ width: 16, height: 16 }} />
          Log out
        </button>
      </div>
    </div>
  )
}

// ── Main export ────────────────────────────────────────────────────────────────

export default function Sidebar() {
  const { studentId } = useAuth()
  const pathname = usePathname()

  const [genome,     setGenome]     = useState<StudentGenome | null>(null)
  const [loading,    setLoading]    = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

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
  // Close drawer on route change
  useEffect(() => { setDrawerOpen(false) }, [pathname])

  const initials = genome?.name ? getInitials(genome.name) : '…'

  return (
    <>
      {/* ── Desktop sidebar (220px) ─────────────────────────────────────────── */}
      <aside className="hidden md:flex fixed left-0 top-0 h-full w-[220px] z-40 flex-col">
        <div className="m-3 flex-1 flex flex-col rounded-3xl bg-white/75 backdrop-blur-xl border border-white/60 shadow-xl shadow-slate-200/50 overflow-hidden">
          <SidebarContent
            genome={genome}
            loading={loading}
            onRefresh={fetchGenome}
            onNavigate={() => {}}
          />
        </div>
      </aside>

      {/* ── Mobile top header bar ───────────────────────────────────────────── */}
      <header className="md:hidden fixed top-0 left-0 right-0 z-50 h-14 bg-white/85 backdrop-blur-xl border-b border-slate-200/60 flex items-center px-4 gap-3">
        {/* Hamburger */}
        <button
          onClick={() => setDrawerOpen(true)}
          className="w-10 h-10 flex items-center justify-center rounded-xl text-slate-600 hover:bg-slate-100 active:scale-90 transition-all duration-150 flex-shrink-0"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Logo / page name */}
        <div className="flex-1 text-sm font-bold text-slate-800 truncate text-center">
          UpMyRank
        </div>

        {/* Avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-[11px] font-bold text-white select-none flex-shrink-0">
          {initials}
        </div>
      </header>

      {/* ── Mobile drawer ───────────────────────────────────────────────────── */}
      <AnimatePresence>
        {drawerOpen && (
          <motion.div
            key="mobile-drawer-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden fixed inset-0 z-[60]"
          >
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-black/30 backdrop-blur-sm"
              onClick={() => setDrawerOpen(false)}
            />

            {/* Drawer panel */}
            <motion.div
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.26, ease: [0.25, 0.1, 0.25, 1] }}
              className="absolute left-0 top-0 h-full w-[300px] max-w-[88vw] bg-white/95 backdrop-blur-xl shadow-2xl z-10 flex flex-col"
            >
              {/* Drawer header */}
              <div className="flex items-center justify-between px-4 pt-4 pb-2 flex-shrink-0">
                <span className="text-sm font-bold text-slate-800">Syllabus</span>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:text-slate-800 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Full sidebar content */}
              <div className="flex-1 min-h-0 overflow-hidden">
                <SidebarContent
                  genome={genome}
                  loading={loading}
                  onRefresh={fetchGenome}
                  onNavigate={() => setDrawerOpen(false)}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
