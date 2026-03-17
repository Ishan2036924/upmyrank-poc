'use client'

import { useState, useCallback, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageCircle, Target, Timer, BarChart3,
  LayoutDashboard, Settings, RefreshCw,
  Flame, BookOpen, CheckCircle, X, Menu,
} from 'lucide-react'
import { apiGet } from '@/lib/api'
import { TEST_STUDENT_ID } from '@/lib/constants'
import { StudentGenome } from '@/lib/types'

// ── Nav items ──────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { label: 'Dashboard',   icon: LayoutDashboard, href: '/' },
  { label: 'Ask a doubt', icon: MessageCircle,   href: '/doubt' },
  { label: 'Practice',    icon: Target,          href: '/practice' },
  { label: 'Mock test',   icon: Timer,           href: '/mock' },
  { label: 'Analytics',  icon: BarChart3,        href: '/progress' },
]

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/** Small pill showing an icon + stat value + label. */
function StatPill({
  icon,
  value,
  label,
  amber = false,
}: {
  icon: React.ReactNode
  value: React.ReactNode
  label: string
  amber?: boolean
}) {
  return (
    <div
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] border ${
        amber
          ? 'bg-amber-950/60 text-amber-300 border-amber-800/40'
          : 'bg-zinc-800 text-zinc-400 border-white/5'
      }`}
    >
      {icon}
      <span className="font-semibold">{value}</span>
      <span className="opacity-70">{label}</span>
    </div>
  )
}

// ── Main Sidebar component ──────────────────────────────────────────────────
export default function Sidebar() {
  const pathname = usePathname()
  const [genome, setGenome] = useState<StudentGenome | null>(null)
  const [loading, setLoading] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  const fetchGenome = useCallback(async () => {
    setLoading(true)
    try {
      setGenome(await apiGet(`/student/${TEST_STUDENT_ID}`))
    } catch (e) {
      console.error('Sidebar: failed to fetch genome', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchGenome() }, [fetchGenome])

  // Close the mobile overlay whenever the route changes
  useEffect(() => { setMobileOpen(false) }, [pathname])

  const initials = genome?.name ? getInitials(genome.name) : '…'
  const STREAK = 1 // placeholder until API exposes streak

  // ── Shared sidebar panel ────────────────────────────────────────────────
  const panel = (
    <div className="flex flex-col h-full bg-zinc-900">

      {/* ── Profile header ─────────────────────────────────────────────── */}
      <div className="px-4 pt-5 pb-4 border-b border-white/5 flex-shrink-0">
        {/* Avatar + name row */}
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 text-xs font-bold text-white select-none">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-zinc-50 truncate">
              {genome?.name ?? 'Loading…'}
            </div>
            <div className="text-xs text-zinc-500">
              {genome?.exam_type ?? 'JEE'} · {genome?.target_year ?? '—'}
            </div>
          </div>
          <button
            onClick={fetchGenome}
            disabled={loading}
            title="Refresh"
            className="flex-shrink-0 text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Stat pills — streak, sessions, resolved */}
        {genome && (
          <div className="flex flex-wrap gap-1.5">
            <StatPill
              icon={<Flame className="h-3 w-3" />}
              value={`${STREAK}d`}
              label="streak"
              amber={STREAK > 0}
            />
            <StatPill
              icon={<BookOpen className="h-3 w-3" />}
              value={genome.total_sessions}
              label="sessions"
            />
            <StatPill
              icon={<CheckCircle className="h-3 w-3" />}
              value={genome.resolved_sessions}
              label="resolved"
            />
          </div>
        )}
      </div>

      {/* ── Core navigation — fills remaining vertical space ───────────── */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ label, icon: Icon, href }) => {
          const active =
            pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                active
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-900/50'
                  : 'text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800/70'
              }`}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* ── Bottom: Settings ────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-white/5 px-3 py-4">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-500 hover:text-zinc-50 hover:bg-zinc-800/70 transition-all duration-150"
        >
          <Settings className="h-4 w-4 flex-shrink-0" />
          Settings
        </Link>
      </div>

    </div>
  )

  return (
    <>
      {/* ── Desktop sidebar (≥ md breakpoint) ──────────────────────────── */}
      <aside className="hidden md:block fixed left-0 top-0 h-full w-[280px] z-40 border-r border-white/5">
        {panel}
      </aside>

      {/* ── Mobile: persistent bottom navigation bar ────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 h-14 bg-zinc-900 border-t border-white/5 flex items-center justify-around px-1">
        {NAV_ITEMS.map(({ icon: Icon, href, label }) => {
          const active =
            pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={`flex flex-col items-center justify-center gap-0.5 min-w-[52px] min-h-[44px] px-2 rounded-lg transition-colors ${
                active ? 'text-indigo-400' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className="text-[10px] font-medium leading-tight">
                {label.split(' ')[0]}
              </span>
            </Link>
          )
        })}
        {/* Menu button opens the slide-over with full profile + nav */}
        <button
          onClick={() => setMobileOpen(true)}
          className={`flex flex-col items-center justify-center gap-0.5 min-w-[52px] min-h-[44px] px-2 rounded-lg transition-colors ${
            mobileOpen ? 'text-indigo-400' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <Menu className="h-5 w-5" />
          <span className="text-[10px] font-medium leading-tight">Menu</span>
        </button>
      </nav>

      {/* ── Mobile: full-screen slide-over overlay ────────────────────────── */}
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
            {/* Backdrop — tap to close */}
            <div
              className="absolute inset-0 bg-black/60"
              onClick={() => setMobileOpen(false)}
            />

            {/* Slide-in panel */}
            <motion.div
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
              className="absolute left-0 top-0 h-full w-[280px] max-w-[85vw] border-r border-white/5 z-10"
            >
              {/* Close button */}
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute top-4 right-3 z-20 w-7 h-7 flex items-center justify-center rounded-full bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
              >
                <X className="h-4 w-4" />
              </button>

              {panel}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
