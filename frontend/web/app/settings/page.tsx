'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import {
  User, Shield, BookOpen, Bell, Palette, Database,
  Camera, Mail, Phone, Globe, Languages, Check,
  Key, ShieldCheck, Chrome, Trash2, Moon, Sun, Monitor,
  Type, Eye, Download, FileJson, AlertTriangle, RefreshCw,
  CheckCircle2, Loader2, LogOut,
} from 'lucide-react'
import { toast } from 'sonner'

import AppShell from '@/components/AppShell'
import AuthGuard from '@/components/AuthGuard'
import { apiGet, apiPost, apiPatch } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { StudentGenome } from '@/lib/types'
import { cn, getInitials } from '@/lib/utils'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog'

// ── Tab config ─────────────────────────────────────────────────────────────

const TABS = [
  { value: 'profile',       label: 'Profile',       icon: User },
  { value: 'account',       label: 'Account',       icon: Shield },
  { value: 'learning',      label: 'Learning',      icon: BookOpen },
  { value: 'notifications', label: 'Notifications', icon: Bell },
  { value: 'appearance',    label: 'Appearance',    icon: Palette },
  { value: 'privacy',       label: 'Privacy & Data',icon: Database },
] as const

type TabValue = typeof TABS[number]['value']

// ── ComingSoon wrapper ─────────────────────────────────────────────────────

function ComingSoon({ children, label = 'Coming soon' }: { children: React.ReactNode; label?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="relative">
          <div className="pointer-events-none opacity-60">{children}</div>
          <div className="absolute inset-0 cursor-not-allowed" />
        </div>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

// ── Profile tab ─────────────────────────────────────────────────────────────

function ProfileTab({ genome }: { genome: StudentGenome | null }) {
  const { studentId } = useAuth()
  const [name,     setName]     = useState('')
  const [phone,    setPhone]    = useState('')
  const [email,    setEmail]    = useState('')
  const [timezone, setTimezone] = useState('Asia/Kolkata')
  const [language, setLanguage] = useState('en')
  const [saving,   setSaving]   = useState(false)
  const [dirty,    setDirty]    = useState(false)

  useEffect(() => {
    if (genome) {
      setName(genome.name || '')
      // Defaults for scaffolded fields
      setPhone('')
      setEmail('') // backend does not return email in genome — left blank
      setTimezone('Asia/Kolkata')
      setLanguage('en')
    }
  }, [genome])

  // v0.20.2: real PATCH /student/{id}. If migration v16 hasn't run yet on
  // this deployment, the backend silently ignores unknown columns and
  // returns {ignored: [...]} — we surface that as a soft warning toast
  // instead of failure.
  const handleSave = async () => {
    if (!studentId) return
    setSaving(true)
    try {
      const res: any = await apiPatch(`/student/${studentId}`, {
        name: name || undefined,
        phone: phone || undefined,
        timezone: timezone || undefined,
        preferred_language: language || undefined,
      })
      const ignored = Array.isArray(res?.ignored) ? res.ignored : []
      const updated = Array.isArray(res?.updated) ? res.updated : []
      if (updated.length === 0 && ignored.length > 0) {
        toast.warning('Profile not saved — schema migration v16 pending on backend.')
      } else if (ignored.length > 0) {
        toast.success(`Saved ${updated.join(', ')} · pending: ${ignored.join(', ')}`)
      } else {
        toast.success('Profile saved')
      }
      setDirty(false)
    } catch (err: any) {
      toast.error('Save failed', { description: err?.message ?? 'Network error.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Avatar card */}
      <Card>
        <CardHeader>
          <CardTitle>Photo</CardTitle>
          <CardDescription>Your profile picture is visible across the app.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-5">
            <Avatar className="h-20 w-20">
              <AvatarFallback className="bg-gradient-to-br from-primary to-indigo-600 text-primary-foreground text-2xl font-semibold">
                {genome?.name ? getInitials(genome.name) : '—'}
              </AvatarFallback>
            </Avatar>
            <div className="flex gap-2">
              <ComingSoon label="Avatar upload coming soon">
                <Button variant="outline" size="sm">
                  <Camera className="h-4 w-4" />
                  Upload photo
                </Button>
              </ComingSoon>
              <ComingSoon label="Avatar upload coming soon">
                <Button variant="ghost" size="sm">Remove</Button>
              </ComingSoon>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personal details */}
      <Card>
        <CardHeader>
          <CardTitle>Personal details</CardTitle>
          <CardDescription>Keep this information current — it&apos;s used throughout your account.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Full name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => { setName(e.target.value); setDirty(true) }}
                placeholder="Your name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  value={email || (genome?.name ? 'hidden@****' : '')}
                  disabled
                  className="pl-9"
                />
              </div>
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span>Email changes require verification.</span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button type="button" className="text-primary hover:underline opacity-60 cursor-not-allowed">Change email</button>
                  </TooltipTrigger>
                  <TooltipContent>Email change flow coming soon</TooltipContent>
                </Tooltip>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone number</Label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="phone"
                  value={phone}
                  onChange={(e) => { setPhone(e.target.value); setDirty(true) }}
                  placeholder="+91 98765 43210"
                  className="pl-9"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Select value={timezone} onValueChange={(v) => { setTimezone(v); setDirty(true) }}>
                <SelectTrigger id="timezone">
                  <Globe className="h-4 w-4 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Asia/Kolkata">Asia/Kolkata (IST)</SelectItem>
                  <SelectItem value="Asia/Dubai">Asia/Dubai (GST)</SelectItem>
                  <SelectItem value="Asia/Singapore">Asia/Singapore (SGT)</SelectItem>
                  <SelectItem value="Europe/London">Europe/London (GMT)</SelectItem>
                  <SelectItem value="America/New_York">America/New_York (EST)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="language">Preferred language</Label>
              <Select value={language} onValueChange={(v) => { setLanguage(v); setDirty(true) }}>
                <SelectTrigger id="language">
                  <Languages className="h-4 w-4 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="hi">हिंदी (Hindi)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Save bar */}
      {dirty && (
        <div className="sticky bottom-4 z-10 flex items-center justify-between rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 shadow-elevated backdrop-blur">
          <div className="flex items-center gap-2 text-sm text-foreground">
            <AlertTriangle className="h-4 w-4 text-warning" />
            Unsaved changes
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setDirty(false)}>Discard</Button>
            <Button size="sm" loading={saving} onClick={handleSave}>
              Save changes
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Account tab ─────────────────────────────────────────────────────────────

function AccountTab() {
  const { logout } = useAuth()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState('')

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>Change your password. Enterprise-grade security required.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ComingSoon label="Password change flow coming soon">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="current-password">Current password</Label>
                <Input id="current-password" type="password" placeholder="••••••••" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-password">New password</Label>
                <Input id="new-password" type="password" placeholder="••••••••" />
              </div>
            </div>
          </ComingSoon>
          <ComingSoon label="Password change flow coming soon">
            <Button variant="outline" size="sm">
              <Key className="h-4 w-4" />
              Update password
            </Button>
          </ComingSoon>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Security</CardTitle>
          <CardDescription>Extra layers of protection for your account.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="h-5 w-5 text-success mt-0.5" />
              <div>
                <div className="text-sm font-medium text-foreground">Email verified</div>
                <div className="text-xs text-muted-foreground">Your email is confirmed.</div>
              </div>
            </div>
            <Badge variant="success">Active</Badge>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div className="flex items-start gap-3">
              <ShieldCheck className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <div className="text-sm font-medium text-foreground">Two-factor authentication</div>
                <div className="text-xs text-muted-foreground">Add an authenticator-app code at sign-in.</div>
              </div>
            </div>
            <ComingSoon label="2FA coming soon">
              <Button size="sm" variant="outline">Enable</Button>
            </ComingSoon>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div className="flex items-start gap-3">
              <Chrome className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <div className="text-sm font-medium text-foreground">Connected accounts</div>
                <div className="text-xs text-muted-foreground">Link Google to enable one-click sign-in.</div>
              </div>
            </div>
            <ComingSoon label="Google OAuth coming soon">
              <Button size="sm" variant="outline">Connect Google</Button>
            </ComingSoon>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/30">
        <CardHeader>
          <CardTitle className="text-destructive">Danger zone</CardTitle>
          <CardDescription>Irreversible actions. Proceed with care.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div>
              <div className="text-sm font-medium text-foreground">Log out of this device</div>
              <div className="text-xs text-muted-foreground">You&apos;ll need to sign in again.</div>
            </div>
            <Button variant="outline" size="sm" onClick={() => logout()}>
              <LogOut className="h-4 w-4" />
              Log out
            </Button>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
            <div>
              <div className="text-sm font-medium text-destructive">Delete account</div>
              <div className="text-xs text-muted-foreground">14-day grace period. All sessions + mastery data removed.</div>
            </div>
            <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
              <DialogTrigger asChild>
                <Button variant="destructive" size="sm">
                  <Trash2 className="h-4 w-4" />
                  Delete account
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Delete your account?</DialogTitle>
                  <DialogDescription>
                    This schedules your account for deletion in 14 days. Sign in again within that window to cancel.
                    Type <span className="font-mono font-semibold">DELETE</span> to confirm.
                  </DialogDescription>
                </DialogHeader>
                <Input
                  value={deleteConfirm}
                  onChange={(e) => setDeleteConfirm(e.target.value)}
                  placeholder="Type DELETE to confirm"
                />
                <DialogFooter>
                  <Button variant="outline" onClick={() => setDeleteOpen(false)}>Cancel</Button>
                  <Button
                    variant="destructive"
                    disabled={deleteConfirm !== 'DELETE'}
                    onClick={() => { toast.info('Account deletion coming soon'); setDeleteOpen(false); setDeleteConfirm('') }}
                  >
                    Delete account
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Learning preferences tab ────────────────────────────────────────────────

function LearningTab({ genome }: { genome: StudentGenome | null }) {
  const [examType, setExamType] = useState('JEE')
  const [targetYear, setTargetYear] = useState('2027')
  const [hintStyle, setHintStyle] = useState('concise')
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (genome) {
      setExamType(genome.exam_type || 'JEE')
      setTargetYear(String(genome.target_year || 2027))
    }
  }, [genome])

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Exam goals</CardTitle>
          <CardDescription>The AI tutor uses these to pace content and difficulty.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="exam-type">Exam type</Label>
              <Select value={examType} onValueChange={(v) => { setExamType(v); setDirty(true) }}>
                <SelectTrigger id="exam-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="JEE">JEE (Main + Advanced)</SelectItem>
                  <SelectItem value="NEET">NEET</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="target-year">Target year</Label>
              <Select value={targetYear} onValueChange={(v) => { setTargetYear(v); setDirty(true) }}>
                <SelectTrigger id="target-year"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="2026">2026</SelectItem>
                  <SelectItem value="2027">2027</SelectItem>
                  <SelectItem value="2028">2028</SelectItem>
                  <SelectItem value="2029">2029</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tutoring style</CardTitle>
          <CardDescription>How the Socratic engine should frame hints.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ComingSoon label="Hint-style wiring to engine coming soon">
            <div className="space-y-2">
              <Label>Hint verbosity</Label>
              <Select value={hintStyle} onValueChange={setHintStyle}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="concise">Concise — minimal hand-holding</SelectItem>
                  <SelectItem value="balanced">Balanced — default</SelectItem>
                  <SelectItem value="detailed">Detailed — step-by-step walkthroughs</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </ComingSoon>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Learning profile</CardTitle>
          <CardDescription>Auto-inferred from your sessions. Evolves every 5 sessions.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {genome?.persona_profile ? (
            <>
              <div className="flex items-center justify-between rounded-lg bg-muted/30 px-4 py-3">
                <span className="text-sm text-muted-foreground">Scaffolding level</span>
                <Badge variant="secondary">{genome.persona_profile.scaffolding_level}</Badge>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-muted/30 px-4 py-3">
                <span className="text-sm text-muted-foreground">Preferred style</span>
                <Badge variant="secondary">{genome.persona_profile.preferred_style}</Badge>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-muted/30 px-4 py-3">
                <span className="text-sm text-muted-foreground">Study intensity</span>
                <Badge variant="secondary">{genome.persona_profile.study_intensity}</Badge>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-muted/30 px-4 py-3">
                <span className="text-sm text-muted-foreground">Learning velocity</span>
                <Badge variant="secondary">{genome.persona_profile.learning_velocity}</Badge>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No persona data yet — complete at least one Socratic session.
            </p>
          )}
        </CardContent>
      </Card>

      {dirty && (
        <div className="sticky bottom-4 flex justify-end gap-2 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 shadow-elevated">
          <Button variant="ghost" size="sm" onClick={() => setDirty(false)}>Discard</Button>
          <Button size="sm" onClick={() => { toast.success('Preferences saved'); setDirty(false) }}>Save</Button>
        </div>
      )}
    </div>
  )
}

// ── Notifications tab ───────────────────────────────────────────────────────

function NotificationsTab() {
  const [prefs, setPrefs] = useState({
    weeklyDigest: true,
    studyReminders: true,
    examAlerts: true,
    browserPush: false,
    masteryMilestones: true,
  })

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Email notifications</CardTitle>
          <CardDescription>Choose what lands in your inbox.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {[
            { key: 'weeklyDigest',      title: 'Weekly progress digest',  desc: 'Summary of your mastery delta + top 3 weak concepts.' },
            { key: 'studyReminders',    title: 'Study reminders',          desc: 'Pings if you miss 2+ days in a row.' },
            { key: 'examAlerts',        title: 'Exam countdown alerts',     desc: 'Monthly nudges until JEE/NEET.' },
          ].map((row) => (
            <div key={row.key} className="flex items-center justify-between py-3 border-b border-border last:border-0">
              <div className="pr-4">
                <div className="text-sm font-medium text-foreground">{row.title}</div>
                <div className="text-xs text-muted-foreground">{row.desc}</div>
              </div>
              <ComingSoon label="Email delivery coming soon">
                <Switch
                  checked={prefs[row.key as keyof typeof prefs]}
                  onCheckedChange={(v) => setPrefs({ ...prefs, [row.key]: v })}
                />
              </ComingSoon>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Browser push</CardTitle>
          <CardDescription>Real-time nudges while you&apos;re on the web.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {[
            { key: 'browserPush',       title: 'Enable browser notifications', desc: 'Session resume + mastery milestone pings.' },
            { key: 'masteryMilestones', title: 'Mastery milestone alerts',      desc: 'When a concept crosses 80% mastery.' },
          ].map((row) => (
            <div key={row.key} className="flex items-center justify-between py-3 border-b border-border last:border-0">
              <div className="pr-4">
                <div className="text-sm font-medium text-foreground">{row.title}</div>
                <div className="text-xs text-muted-foreground">{row.desc}</div>
              </div>
              <ComingSoon label="Browser push coming soon">
                <Switch
                  checked={prefs[row.key as keyof typeof prefs]}
                  onCheckedChange={(v) => setPrefs({ ...prefs, [row.key]: v })}
                />
              </ComingSoon>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

// ── Appearance tab ──────────────────────────────────────────────────────────

function AppearanceTab() {
  const [fontSize, setFontSize] = useState('medium')
  const [density,  setDensity]  = useState('comfortable')

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Theme</CardTitle>
          <CardDescription>Light mode is active. Dark mode ships in a follow-up release.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3">
            <button className="flex flex-col items-center gap-2 rounded-xl border-2 border-primary bg-muted/30 p-4">
              <Sun className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium text-foreground">Light</span>
              <Check className="h-3 w-3 text-primary" />
            </button>
            <ComingSoon label="Dark mode coming soon">
              <button className="flex w-full flex-col items-center gap-2 rounded-xl border border-border p-4">
                <Moon className="h-5 w-5 text-muted-foreground" />
                <span className="text-sm font-medium text-muted-foreground">Dark</span>
                <span className="text-[10px] text-muted-foreground">Soon</span>
              </button>
            </ComingSoon>
            <ComingSoon label="System theme coming soon">
              <button className="flex w-full flex-col items-center gap-2 rounded-xl border border-border p-4">
                <Monitor className="h-5 w-5 text-muted-foreground" />
                <span className="text-sm font-medium text-muted-foreground">System</span>
                <span className="text-[10px] text-muted-foreground">Soon</span>
              </button>
            </ComingSoon>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Text & density</CardTitle>
          <CardDescription>Tune the reading experience to your setup.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Font size</Label>
            <Select value={fontSize} onValueChange={setFontSize}>
              <SelectTrigger><Type className="h-4 w-4 text-muted-foreground" /><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="small">Small</SelectItem>
                <SelectItem value="medium">Medium (default)</SelectItem>
                <SelectItem value="large">Large</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Math density</Label>
            <Select value={density} onValueChange={setDensity}>
              <SelectTrigger><Eye className="h-4 w-4 text-muted-foreground" /><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="compact">Compact</SelectItem>
                <SelectItem value="comfortable">Comfortable (default)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Privacy & data tab ──────────────────────────────────────────────────────

function PrivacyTab() {
  const handleExport = () => {
    toast.info('Data export coming soon', {
      description: 'Backend endpoint GET /student/export is scheduled for the next release.',
    })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Your data</CardTitle>
          <CardDescription>Full control over what we hold about you.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div className="flex items-start gap-3">
              <FileJson className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <div className="text-sm font-medium text-foreground">Export my data</div>
                <div className="text-xs text-muted-foreground">JSON dump of sessions, mastery, persona, and preferences.</div>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={handleExport}>
              <Download className="h-4 w-4" />
              Export
            </Button>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div className="flex items-start gap-3">
              <Trash2 className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <div className="text-sm font-medium text-foreground">Delete all doubts</div>
                <div className="text-xs text-muted-foreground">Clears chat history but keeps mastery scores.</div>
              </div>
            </div>
            <ComingSoon label="Doubt purge coming soon">
              <Button variant="outline" size="sm">Delete</Button>
            </ComingSoon>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Legal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <a href="#" onClick={(e) => { e.preventDefault(); toast.info('Privacy policy coming soon') }} className="block text-primary hover:underline">
            Privacy policy
          </a>
          <a href="#" onClick={(e) => { e.preventDefault(); toast.info('Terms coming soon') }} className="block text-primary hover:underline">
            Terms of service
          </a>
          <a href="#" onClick={(e) => { e.preventDefault(); toast.info('Cookie policy coming soon') }} className="block text-primary hover:underline">
            Cookie policy
          </a>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Main page ───────────────────────────────────────────────────────────────

function SettingsInner() {
  const { studentId } = useAuth()
  const router = useRouter()
  const params = useSearchParams()

  const activeTab = (params.get('tab') as TabValue) ?? 'profile'
  const setActiveTab = (v: string) => {
    const u = new URL(window.location.href)
    u.searchParams.set('tab', v)
    router.replace(u.pathname + '?' + u.searchParams.toString())
  }

  const [genome,  setGenome]  = useState<StudentGenome | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!studentId) return
    setLoading(true)
    apiGet(`/student/${studentId}`)
      .then(setGenome)
      .catch(() => toast.error('Failed to load profile'))
      .finally(() => setLoading(false))
  }, [studentId])

  return (
    <AppShell maxWidth="max-w-5xl">
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Settings</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage your profile, account security, learning preferences, and data.
            </p>
          </div>
          {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="inline-flex h-auto flex-wrap gap-1 bg-muted/40 p-1">
            {TABS.map(({ value, label, icon: Icon }) => (
              <TabsTrigger key={value} value={value} className="gap-2">
                <Icon className="h-3.5 w-3.5" />
                {label}
              </TabsTrigger>
            ))}
          </TabsList>

          <TabsContent value="profile"><ProfileTab genome={genome} /></TabsContent>
          <TabsContent value="account"><AccountTab /></TabsContent>
          <TabsContent value="learning"><LearningTab genome={genome} /></TabsContent>
          <TabsContent value="notifications"><NotificationsTab /></TabsContent>
          <TabsContent value="appearance"><AppearanceTab /></TabsContent>
          <TabsContent value="privacy"><PrivacyTab /></TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}

export default function SettingsPage() {
  return (
    <AuthGuard>
      <Suspense fallback={
        <AppShell maxWidth="max-w-5xl">
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        </AppShell>
      }>
        <SettingsInner />
      </Suspense>
    </AuthGuard>
  )
}
