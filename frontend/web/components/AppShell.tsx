'use client'

/**
 * AppShell — Enterprise-grade layout shell for all logged-in pages.
 *
 * Layout:
 * - Left sidebar (collapsible, 260px): logo + primary nav + subject syllabus + profile card
 * - Top bar: page title + search (⌘K scaffold) + notifications + avatar menu
 * - Main content area with max-w-7xl + padding
 * - Mobile: sidebar becomes drawer, top bar collapses
 */

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname, useRouter } from 'next/navigation'
import {
  Home, MessageSquare, Target, Timer, BarChart3, Settings as SettingsIcon,
  Shield, LogOut, Menu, X, Bell, Search, ChevronDown, User,
  Sparkles, HelpCircle,
} from 'lucide-react'

import { apiGet } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { StudentGenome } from '@/lib/types'
import { cn, getInitials } from '@/lib/utils'
import TopicTree from '@/components/TopicTree'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'

// ── Nav items ───────────────────────────────────────────────────────────────

interface NavItem {
  label: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  exact?: boolean
}

const PRIMARY_NAV: NavItem[] = [
  { label: 'Home',      href: '/',         icon: Home, exact: true },
  { label: 'Doubts',    href: '/doubt',    icon: MessageSquare },
  { label: 'Practice',  href: '/practice', icon: Target },
  { label: 'Mock Test', href: '/mock',     icon: Timer },
  { label: 'Progress',  href: '/progress', icon: BarChart3 },
]

const SECONDARY_NAV: NavItem[] = [
  { label: 'Settings', href: '/settings', icon: SettingsIcon },
]

// ── Page title resolver (for topbar breadcrumb) ─────────────────────────────

function getPageTitle(pathname: string): string {
  if (pathname === '/') return 'Home'
  if (pathname.startsWith('/doubt'))    return 'Doubts'
  if (pathname.startsWith('/practice')) return 'Practice'
  if (pathname.startsWith('/mock'))     return 'Mock Test'
  if (pathname.startsWith('/progress')) return 'Progress'
  if (pathname.startsWith('/settings')) return 'Settings'
  if (pathname.startsWith('/admin'))    return 'Admin'
  return ''
}

// ── Sidebar body (shared by desktop + mobile drawer) ────────────────────────

function SidebarBody({
  genome,
  isAdmin,
  onNavigate,
  onLogout,
}: {
  genome: StudentGenome | null
  isAdmin: boolean
  onNavigate: () => void
  onLogout: () => void
}) {
  const pathname = usePathname()

  const isActive = (item: NavItem) =>
    item.exact ? pathname === item.href : pathname.startsWith(item.href)

  return (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-indigo-600 shadow-soft">
          <Sparkles className="h-4 w-4 text-primary-foreground" />
        </div>
        <div className="flex flex-col leading-none">
          <span className="text-sm font-bold tracking-tight text-foreground">UpMyRank</span>
          <span className="text-[10px] font-medium text-muted-foreground">AI Tutor · Enterprise</span>
        </div>
      </div>

      {/* Primary nav */}
      <nav className="mt-2 flex-1 overflow-hidden px-3">
        <div className="space-y-0.5">
          {PRIMARY_NAV.map((item) => {
            const active = isActive(item)
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span className="flex-1">{item.label}</span>
              </Link>
            )
          })}
        </div>

        {/* Syllabus tree */}
        <div className="mt-5 border-t border-border pt-4">
          <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Syllabus
          </div>
          <div className="relative h-[280px]">
            <TopicTree onNavigate={onNavigate} />
          </div>
        </div>
      </nav>

      {/* Secondary + profile */}
      <div className="border-t border-border px-3 py-3">
        <div className="space-y-0.5">
          {SECONDARY_NAV.map((item) => {
            const active = isActive(item)
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            )
          })}
          {isAdmin && (
            <Link
              href="/admin"
              onClick={onNavigate}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                pathname.startsWith('/admin')
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <Shield className="h-4 w-4" />
              <span className="flex-1">Admin</span>
              <Badge variant="secondary" className="text-[9px]">INTERNAL</Badge>
            </Link>
          )}
        </div>

        {/* Profile card */}
        <div className="mt-3 rounded-xl border border-border bg-card p-3">
          <div className="flex items-center gap-3">
            <Avatar className="h-9 w-9">
              <AvatarFallback className="bg-gradient-to-br from-primary to-indigo-600 text-primary-foreground text-xs font-semibold">
                {genome?.name ? getInitials(genome.name) : '…'}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-foreground">
                {genome?.name ?? 'Loading…'}
              </div>
              <div className="truncate text-[11px] text-muted-foreground">
                {genome?.exam_type ?? 'JEE'} · {genome?.target_year ?? '—'}
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onLogout}
              className="h-7 w-7 text-muted-foreground hover:text-destructive"
              title="Log out"
            >
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Top bar ─────────────────────────────────────────────────────────────────

function Topbar({
  genome,
  onMenuClick,
  pageTitle,
  onLogout,
}: {
  genome: StudentGenome | null
  onMenuClick: () => void
  pageTitle: string
  onLogout: () => void
}) {
  const router = useRouter()

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-xl md:px-6">
      {/* Mobile hamburger */}
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={onMenuClick}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </Button>

      {/* Page title (desktop) */}
      <div className="hidden md:flex items-baseline gap-2 min-w-0">
        <h1 className="text-[15px] font-semibold text-foreground truncate">{pageTitle}</h1>
      </div>

      {/* Mobile logo center */}
      <div className="flex-1 text-center text-sm font-semibold text-foreground md:hidden">
        UpMyRank
      </div>

      {/* Search (desktop) */}
      <div className="hidden md:flex flex-1 max-w-md mx-4">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => toast.info('Command palette coming soon', { description: 'Quick jump to any topic or doubt from here.' })}
              className="group flex h-9 w-full items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 text-sm text-muted-foreground transition-colors hover:bg-muted"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="flex-1 text-left">Search topics, doubts…</span>
              <kbd className="hidden rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-mono font-semibold md:inline-flex">⌘K</kbd>
            </button>
          </TooltipTrigger>
          <TooltipContent>Command palette — coming soon</TooltipContent>
        </Tooltip>
      </div>

      {/* Right cluster */}
      <div className="ml-auto flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => toast.info('Notifications coming soon', { description: "We'll ping you when new problems match your weak areas." })}
            >
              <Bell className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Notifications — coming soon</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => toast.info('Help center coming soon')}
            >
              <HelpCircle className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Help</TooltipContent>
        </Tooltip>

        {/* Avatar menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-9 gap-2 px-2">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="bg-gradient-to-br from-primary to-indigo-600 text-primary-foreground text-[10px] font-semibold">
                  {genome?.name ? getInitials(genome.name) : '…'}
                </AvatarFallback>
              </Avatar>
              <ChevronDown className="hidden md:inline h-3 w-3 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col gap-0.5 py-2">
              <span className="text-sm font-semibold">{genome?.name ?? '—'}</span>
              <span className="text-[11px] font-normal text-muted-foreground">
                {genome?.exam_type} · {genome?.target_year}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push('/settings')}>
              <User className="h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push('/settings?tab=account')}>
              <SettingsIcon className="h-4 w-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onLogout} className="text-destructive focus:text-destructive">
              <LogOut className="h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}

// ── Main export ─────────────────────────────────────────────────────────────

export interface AppShellProps {
  children: React.ReactNode
  /** If true, main content area uses full viewport height (chat pages) */
  fullHeight?: boolean
  /** Optional right-side context panel (used by /doubt) */
  rightPanel?: React.ReactNode
  /** Custom max-width; default max-w-6xl */
  maxWidth?: string
}

export default function AppShell({
  children,
  fullHeight = false,
  rightPanel,
  maxWidth = 'max-w-6xl',
}: AppShellProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { studentId, logout } = useAuth()

  const [genome, setGenome] = useState<StudentGenome | null>(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    if (!studentId) return
    apiGet(`/student/${studentId}`)
      .then(setGenome)
      .catch(() => {})
    apiGet('/admin/is_admin')
      .then((d: any) => setIsAdmin(!!d?.is_admin))
      .catch(() => {})
  }, [studentId])

  // Close drawer on route change
  useEffect(() => { setDrawerOpen(false) }, [pathname])

  const handleLogout = useCallback(() => {
    logout()
  }, [logout])

  const pageTitle = getPageTitle(pathname)

  return (
    <div className="flex h-[100dvh] bg-muted/20">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-[260px] shrink-0 border-r border-border bg-card">
        <SidebarBody
          genome={genome}
          isAdmin={isAdmin}
          onNavigate={() => {}}
          onLogout={handleLogout}
        />
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full w-[280px] max-w-[85vw] bg-card shadow-floating">
            <div className="flex items-center justify-between px-4 pt-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Menu
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close menu"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <SidebarBody
              genome={genome}
              isAdmin={isAdmin}
              onNavigate={() => setDrawerOpen(false)}
              onLogout={handleLogout}
            />
          </div>
        </div>
      )}

      {/* Main + right panel */}
      <div className="flex flex-1 min-w-0 flex-col">
        <Topbar
          genome={genome}
          onMenuClick={() => setDrawerOpen(true)}
          pageTitle={pageTitle}
          onLogout={handleLogout}
        />

        <div className="flex flex-1 min-h-0 overflow-hidden">
          <main
            className={cn(
              'flex-1 min-w-0',
              fullHeight ? 'overflow-hidden' : 'overflow-y-auto',
            )}
          >
            {fullHeight ? (
              children
            ) : (
              <div className={cn('mx-auto px-4 py-6 md:px-6 md:py-8', maxWidth)}>
                {children}
              </div>
            )}
          </main>

          {rightPanel && (
            <aside className="hidden lg:flex w-[320px] shrink-0 border-l border-border bg-card overflow-y-auto">
              {rightPanel}
            </aside>
          )}
        </div>
      </div>
    </div>
  )
}
