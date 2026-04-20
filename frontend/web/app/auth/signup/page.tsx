'use client'

import { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, Sparkles, Mail, Lock, User, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/lib/auth'
import { pingBackend } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function passwordStrength(pw: string): { score: number; label: string; color: string } {
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[A-Z]/.test(pw)) score++
  if (/[0-9]/.test(pw)) score++
  if (/[^A-Za-z0-9]/.test(pw)) score++
  if (score <= 1) return { score: 1, label: 'Weak',     color: 'bg-destructive' }
  if (score <= 3) return { score: 3, label: 'Decent',   color: 'bg-warning' }
  return              { score: 5, label: 'Strong',   color: 'bg-success' }
}

export default function SignupPage() {
  const router = useRouter()
  const { login } = useAuth()

  useEffect(() => { pingBackend() }, [])

  const [name,       setName]       = useState('')
  const [email,      setEmail]      = useState('')
  const [password,   setPassword]   = useState('')
  const [showPass,   setShowPass]   = useState(false)
  const [examType,   setExamType]   = useState('JEE')
  const [targetYear, setTargetYear] = useState('2027')
  const [error,      setError]      = useState<string | null>(null)
  const [loading,    setLoading]    = useState(false)

  const strength = useMemo(() => passwordStrength(password), [password])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, exam_type: examType, target_year: Number(targetYear) }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || 'Signup failed')
      }
      const data = await res.json()

      if (data.token) {
        login(data.token, data.student_id, data.name ?? name, data.refresh_token)
        toast.success("Account created — let's set you up")
        router.push('/onboarding')
      } else {
        toast.info('Confirm your email to continue')
        router.push('/auth/login?confirm=1')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      let display = msg
      try {
        const parsed = JSON.parse(msg)
        display = parsed.detail ?? msg
      } catch {}
      setError(display)
      toast.error(display)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[100dvh] grid grid-cols-1 lg:grid-cols-2">
      {/* Left: hero */}
      <div className="hidden lg:flex flex-col justify-between bg-gradient-to-br from-primary/10 via-indigo-50 to-background p-12 border-r border-border">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-indigo-600 shadow-soft">
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </div>
          <div className="text-sm font-bold text-foreground">UpMyRank</div>
        </div>

        <div className="max-w-md space-y-5">
          <h2 className="text-3xl font-bold tracking-tight text-foreground leading-tight">
            Start your rank-boost journey in <span className="text-primary">60 seconds</span>.
          </h2>
          <p className="text-base text-muted-foreground leading-relaxed">
            Create an account, answer 4 quick questions, and your personalised Socratic tutor is ready.
          </p>
          <ul className="space-y-2 pt-2">
            {[
              'Misconception detection built in',
              'Every response Socratic — never spoon-fed',
              'Persona evolves every 5 sessions',
            ].map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-foreground">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} UpMyRank
        </p>
      </div>

      {/* Right: form */}
      <div className="flex items-center justify-center p-6 md:p-12">
        <Card className="w-full max-w-md border-0 shadow-none md:border md:shadow-soft">
          <CardHeader className="space-y-2 text-center lg:text-left">
            <div className="lg:hidden flex justify-center mb-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-indigo-600 shadow-soft">
                <Sparkles className="h-5 w-5 text-primary-foreground" />
              </div>
            </div>
            <CardTitle className="text-2xl">Create your account</CardTitle>
            <CardDescription>Free while we&apos;re in beta. No card required.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Full name</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required disabled={loading} placeholder="Arjun Sharma" className="pl-9" />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required disabled={loading} placeholder="you@example.com" className="pl-9" />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPass ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    disabled={loading}
                    placeholder="At least 8 characters"
                    className="pl-9 pr-10"
                  />
                  <button type="button" onClick={() => setShowPass((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {password && (
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                      <div className={cn('h-full transition-all', strength.color)} style={{ width: `${(strength.score / 5) * 100}%` }} />
                    </div>
                    <span className="text-[11px] text-muted-foreground w-14 text-right">{strength.label}</span>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="exam">Exam</Label>
                  <Select value={examType} onValueChange={setExamType}>
                    <SelectTrigger id="exam"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="JEE">JEE</SelectItem>
                      <SelectItem value="NEET">NEET</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="year">Target year</Label>
                  <Select value={targetYear} onValueChange={setTargetYear}>
                    <SelectTrigger id="year"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {['2026', '2027', '2028', '2029'].map((y) => (
                        <SelectItem key={y} value={y}>{y}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                className="w-full"
                size="lg"
                loading={loading}
                disabled={!name || !email || !password}
              >
                Create account
                <ArrowRight className="h-4 w-4" />
              </Button>

              <p className="text-[11px] text-muted-foreground text-center">
                By creating an account, you agree to our Terms and Privacy Policy.
              </p>
            </form>

            <p className="text-center text-sm text-muted-foreground mt-6">
              Already have an account?{' '}
              <Link href="/auth/login" className="text-primary font-medium hover:underline">
                Sign in
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
