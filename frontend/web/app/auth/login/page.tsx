'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Eye, EyeOff, Sparkles, Mail, Lock, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

import { useAuth } from '@/lib/auth'
import { pingBackend } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()

  useEffect(() => { pingBackend() }, [])

  const [email,       setEmail]       = useState('')
  const [password,    setPassword]    = useState('')
  const [showPass,    setShowPass]    = useState(false)
  const [capsOn,      setCapsOn]      = useState(false)
  const [error,       setError]       = useState<string | null>(null)
  const [loading,     setLoading]     = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || 'Login failed')
      }
      const data = await res.json()
      let name = ''
      try {
        const meRes = await fetch(`${API_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${data.token}` },
        })
        if (meRes.ok) {
          const me = await meRes.json()
          name = me.name ?? ''
        }
      } catch { /* non-fatal */ }

      login(data.token, data.student_id, name, data.refresh_token)
      toast.success(`Welcome back${name ? `, ${name.split(' ')[0]}` : ''}`)

      try {
        const onbRes = await fetch(`${API_URL}/onboarding/status`, {
          headers: { Authorization: `Bearer ${data.token}` },
        })
        if (onbRes.ok) {
          const onb = await onbRes.json()
          router.push(onb.onboarding_completed ? '/' : '/onboarding')
        } else {
          router.push('/')
        }
      } catch {
        router.push('/')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      let display = msg
      try {
        const parsed = JSON.parse(msg)
        display = parsed.detail ?? msg
      } catch { /* noop */ }
      setError(display)
      toast.error(display)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[100dvh] grid grid-cols-1 lg:grid-cols-2">
      {/* Left: marketing hero (desktop only) */}
      <div className="hidden lg:flex flex-col justify-between bg-gradient-to-br from-primary/10 via-indigo-50 to-background p-12 border-r border-border">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-indigo-600 shadow-soft">
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </div>
          <div className="text-sm font-bold text-foreground">UpMyRank</div>
        </div>

        <div className="max-w-md space-y-5">
          <h2 className="text-3xl font-bold tracking-tight text-foreground leading-tight">
            The AI tutor that actually makes you <span className="text-primary">think</span>.
          </h2>
          <p className="text-base text-muted-foreground leading-relaxed">
            Socratic hints, misconception detection, and a persona that evolves with every session.
            Built for JEE and NEET aspirants serious about rank.
          </p>
          <div className="grid grid-cols-3 gap-3 pt-4">
            {[
              { n: '15K+',  t: 'NCERT chunks'    },
              { n: '3',     t: 'Subjects'        },
              { n: '20+',   t: 'PYQs indexed'    },
            ].map((stat) => (
              <div key={stat.t} className="rounded-xl border border-border bg-card p-4">
                <div className="text-xl font-bold text-foreground">{stat.n}</div>
                <div className="text-[11px] text-muted-foreground mt-1">{stat.t}</div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} UpMyRank · Physics · Chemistry · Maths
        </p>
      </div>

      {/* Right: sign-in form */}
      <div className="flex items-center justify-center p-6 md:p-12">
        <Card className="w-full max-w-md border-0 shadow-none md:border md:shadow-soft">
          <CardHeader className="space-y-2 text-center lg:text-left">
            <div className="lg:hidden flex justify-center mb-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-indigo-600 shadow-soft">
                <Sparkles className="h-5 w-5 text-primary-foreground" />
              </div>
            </div>
            <CardTitle className="text-2xl">Welcome back</CardTitle>
            <CardDescription>Sign in to continue your prep.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                    placeholder="you@example.com"
                    className="pl-9"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Password</Label>
                  <Link href="/auth/forgot-password" className="text-xs text-primary hover:underline">
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPass ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyUp={(e) => setCapsOn(e.getModifierState?.('CapsLock') ?? false)}
                    required
                    disabled={loading}
                    placeholder="••••••••"
                    className="pl-9 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label={showPass ? 'Hide password' : 'Show password'}
                  >
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {capsOn && (
                  <p className="text-[11px] text-warning">⚠ Caps Lock is on.</p>
                )}
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
                disabled={!email || !password}
              >
                Sign in
                <ArrowRight className="h-4 w-4" />
              </Button>

              <div className="relative py-2">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">or</span>
                </div>
              </div>

              <Tooltip>
                <TooltipTrigger asChild>
                  <div>
                    <Button type="button" variant="outline" className="w-full" disabled>
                      <svg className="h-4 w-4" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                      </svg>
                      Continue with Google
                    </Button>
                  </div>
                </TooltipTrigger>
                <TooltipContent>Coming soon</TooltipContent>
              </Tooltip>
            </form>

            <p className="text-center text-sm text-muted-foreground mt-6">
              New here?{' '}
              <Link href="/auth/signup" className="text-primary font-medium hover:underline">
                Create an account
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
