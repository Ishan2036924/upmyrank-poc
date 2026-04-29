'use client'

import { useState, useEffect, Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  Eye, EyeOff, Sparkles, Mail, Lock, ArrowRight,
  Atom, FlaskConical, Calculator, Zap, Target, Lightbulb, GraduationCap,
} from 'lucide-react'
import { toast } from 'sonner'
import { motion, useReducedMotion, AnimatePresence } from 'framer-motion'

import { useAuth } from '@/lib/auth'
import { pingBackend } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── v0.20.13 — premium login page ─────────────────────────────────────────────
// Light glassmorphic per UI_PRO_MAX.md (no dark mode). Framer-motion drives:
//   • mesh-gradient background that drifts on a 24s loop
//   • 3 floating glass orbs at randomised offsets
//   • staggered hero text + stat-card reveal
//   • animated subject "atoms" floating around the marketing area
//   • spring-y form field focus + inline label scale
//   • shake on submit error, scale-bounce on success
// All animations honour `useReducedMotion`.

// ── Animation primitives ──────────────────────────────────────────────────────
const EASE_OUT_EXPO: [number, number, number, number] = [0.16, 1, 0.3, 1]

const containerStagger = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.15 } },
}

const fadeUp = {
  hidden:  { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.7, ease: EASE_OUT_EXPO } },
}

const fadeIn = {
  hidden:  { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.6, ease: EASE_OUT_EXPO } },
}

// ── Suspense wrapper (Next.js 16 prerender requirement) ──────────────────────
export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[100dvh] grid place-items-center bg-gradient-to-br from-violet-50 via-white to-indigo-50">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 animate-pulse shadow-lg shadow-indigo-200/60" />
            <p className="text-sm text-slate-400">Loading…</p>
          </div>
        </div>
      }
    >
      <LoginPageInner />
    </Suspense>
  )
}

function LoginPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login } = useAuth()
  const prefersReducedMotion = useReducedMotion()

  useEffect(() => { pingBackend() }, [])

  // Session-expired toast (v0.20.12)
  useEffect(() => {
    const reason = searchParams.get('reason')
    if (reason === 'session_expired') {
      toast.info('Your session expired. Please log in again.', {
        description: "We rotate tokens for security; this isn't a bug.",
        duration: 6000,
      })
    }
  }, [searchParams])

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [capsOn,   setCapsOn]   = useState(false)
  const [error,    setError]    = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)

  // For inline focus animation (drives label scale + ring colour)
  const [emailFocus,    setEmailFocus]    = useState(false)
  const [passwordFocus, setPasswordFocus] = useState(false)
  // Shake on error
  const [shakeKey, setShakeKey] = useState(0)

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
      setShakeKey((k) => k + 1)
      toast.error(display)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-[100dvh] overflow-hidden grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] bg-gradient-to-br from-violet-50 via-white to-indigo-50">
      {/* ── Animated mesh-gradient background ─────────────────────────────── */}
      <BackgroundLayer reduced={!!prefersReducedMotion} />

      {/* ── Left: marketing hero (desktop only) ──────────────────────────── */}
      <motion.section
        variants={containerStagger}
        initial="hidden"
        animate="visible"
        className="relative hidden lg:flex flex-col justify-between p-12 xl:p-16 z-10"
      >
        {/* logo */}
        <motion.div variants={fadeUp} className="flex items-center gap-3">
          <div className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 via-indigo-500 to-blue-500 shadow-lg shadow-indigo-300/40">
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-violet-500/40 via-indigo-500/40 to-blue-500/40 blur-xl" aria-hidden />
            {/* v0.20.14 — pulse-ring rippling outward from the logo on a 2.4s
                loop. Three concentric rings phased 0/0.8/1.6s give a continuous
                "live signal" feel without flashing. */}
            <motion.div
              aria-hidden
              className="absolute inset-0 rounded-2xl border-2 border-indigo-400/50"
              animate={{ scale: [1, 1.6], opacity: [0.6, 0] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeOut' }}
            />
            <motion.div
              aria-hidden
              className="absolute inset-0 rounded-2xl border-2 border-violet-400/50"
              animate={{ scale: [1, 1.6], opacity: [0.6, 0] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeOut', delay: 0.8 }}
            />
            <Sparkles className="relative h-5 w-5 text-white" />
          </div>
          <div>
            <div className="text-base font-extrabold tracking-tight text-slate-900">UpMyRank</div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">AI Tutor · JEE / NEET</div>
          </div>
        </motion.div>

        {/* headline */}
        <div className="max-w-xl space-y-7">
          <motion.div variants={fadeUp}>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-200/60 bg-white/70 backdrop-blur-md px-3 py-1 text-[11px] font-semibold text-violet-700 shadow-[0_4px_18px_rgb(139,92,246,0.08)]">
              <Zap className="h-3 w-3" />
              Built for serious aspirants
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="text-4xl xl:text-5xl font-bold tracking-tight text-slate-900 leading-[1.05]"
          >
            The AI tutor that actually makes you{' '}
            <span className="relative inline-block">
              <span className="relative z-10 bg-gradient-to-r from-violet-600 via-indigo-600 to-blue-600 bg-clip-text text-transparent">
                think
              </span>
              <motion.span
                className="absolute -bottom-1 left-0 right-0 h-3 bg-gradient-to-r from-violet-200/70 via-indigo-200/70 to-blue-200/70 rounded-full -z-0"
                initial={{ scaleX: 0, transformOrigin: 'left' }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.9, delay: 0.7, ease: EASE_OUT_EXPO }}
              />
              {/* v0.20.14 — sparkle particles emitted around "think" once the
                  underline finishes drawing. Reads as "this is the moment the
                  insight clicks." Six little sparkles fly outward + fade. */}
              <SparkleEmit />
            </span>
            .
          </motion.h1>

          <motion.p variants={fadeUp} className="text-base xl:text-lg text-slate-600 leading-relaxed">
            Socratic hints. A tutor that adapts to how you learn. Built for the rank you
            actually want, not the answer you could just google.
          </motion.p>

          {/* live demo chat preview */}
          <motion.div variants={fadeUp}>
            <ChatPreview />
          </motion.div>

          {/* student-facing benefits (replaces engineer-facing stat cards) */}
          <motion.div variants={fadeUp} className="grid grid-cols-3 gap-3 pt-1">
            {BENEFITS.map((b) => (
              <BenefitCard key={b.label} {...b} />
            ))}
          </motion.div>

          {/* subject pills */}
          <motion.div variants={fadeUp} className="flex items-center gap-2 pt-2">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">Covers:</span>
            <SubjectPill icon={<Atom className="h-3.5 w-3.5" />} label="Physics" tone="indigo" />
            <SubjectPill icon={<FlaskConical className="h-3.5 w-3.5" />} label="Chemistry" tone="emerald" />
            <SubjectPill icon={<Calculator className="h-3.5 w-3.5" />} label="Maths" tone="violet" />
          </motion.div>
        </div>

        <motion.p variants={fadeIn} className="text-[11px] text-slate-400">
          © {new Date().getFullYear()} UpMyRank · For JEE & NEET aspirants
        </motion.p>
      </motion.section>

      {/* ── Right: glassmorphic sign-in form ─────────────────────────────── */}
      <motion.section
        variants={containerStagger}
        initial="hidden"
        animate="visible"
        className="relative flex items-center justify-center p-6 md:p-12 z-10"
      >
        <motion.div
          key={shakeKey}
          animate={shakeKey > 0 && !prefersReducedMotion ? {
            x: [0, -8, 8, -6, 6, -3, 3, 0],
          } : {}}
          transition={{ duration: 0.4, ease: 'easeInOut' }}
          className="w-full max-w-md"
        >
          {/* mobile logo */}
          <motion.div variants={fadeUp} className="lg:hidden flex justify-center mb-6">
            <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 via-indigo-500 to-blue-500 shadow-lg shadow-indigo-300/40">
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-violet-500/40 via-indigo-500/40 to-blue-500/40 blur-xl" aria-hidden />
              <Sparkles className="relative h-6 w-6 text-white" />
            </div>
          </motion.div>

          {/* glass card */}
          <motion.div
            variants={fadeUp}
            className="relative rounded-3xl border border-white/60 bg-white/80 backdrop-blur-xl p-7 md:p-9 shadow-[0_20px_70px_-20px_rgb(99,102,241,0.25),0_8px_24px_-8px_rgb(0,0,0,0.04)]"
          >
            <div className="space-y-1.5 mb-7">
              <h2 className="text-[1.7rem] font-bold tracking-tight text-slate-900 leading-tight">
                Welcome back.
              </h2>
              <p className="text-sm text-slate-500">Sign in to continue your prep.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Email */}
              <div className="space-y-1.5">
                <Label
                  htmlFor="email"
                  className={`text-[13px] font-medium transition-colors duration-200 ${
                    emailFocus ? 'text-indigo-600' : 'text-slate-600'
                  }`}
                >
                  Email
                </Label>
                <div className="relative group">
                  <motion.div
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 z-10 pointer-events-none"
                    animate={{
                      color: emailFocus ? '#6366F1' : '#94A3B8',
                      scale: emailFocus ? 1.05 : 1,
                    }}
                    transition={{ duration: 0.2, ease: EASE_OUT_EXPO }}
                  >
                    <Mail className="h-4 w-4" />
                  </motion.div>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onFocus={() => setEmailFocus(true)}
                    onBlur={() => setEmailFocus(false)}
                    required
                    disabled={loading}
                    placeholder="you@example.com"
                    className="pl-10 h-11 bg-white/70 border-slate-200/80 rounded-xl text-[15px] placeholder:text-slate-400 focus-visible:border-indigo-400 focus-visible:ring-4 focus-visible:ring-indigo-100/70 transition-all duration-200"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label
                    htmlFor="password"
                    className={`text-[13px] font-medium transition-colors duration-200 ${
                      passwordFocus ? 'text-indigo-600' : 'text-slate-600'
                    }`}
                  >
                    Password
                  </Label>
                  <Link
                    href="/auth/forgot-password"
                    className="text-[12px] text-indigo-600 hover:text-indigo-800 font-medium transition-colors duration-200"
                  >
                    Forgot?
                  </Link>
                </div>
                <div className="relative group">
                  <motion.div
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 z-10 pointer-events-none"
                    animate={{
                      color: passwordFocus ? '#6366F1' : '#94A3B8',
                      scale: passwordFocus ? 1.05 : 1,
                    }}
                    transition={{ duration: 0.2, ease: EASE_OUT_EXPO }}
                  >
                    <Lock className="h-4 w-4" />
                  </motion.div>
                  <Input
                    id="password"
                    type={showPass ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onFocus={() => setPasswordFocus(true)}
                    onBlur={() => setPasswordFocus(false)}
                    onKeyUp={(e) => setCapsOn(e.getModifierState?.('CapsLock') ?? false)}
                    required
                    disabled={loading}
                    placeholder="••••••••"
                    className="pl-10 pr-11 h-11 bg-white/70 border-slate-200/80 rounded-xl text-[15px] placeholder:text-slate-400 focus-visible:border-indigo-400 focus-visible:ring-4 focus-visible:ring-indigo-100/70 transition-all duration-200"
                  />
                  <motion.button
                    type="button"
                    onClick={() => setShowPass((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 transition-colors duration-200 active:scale-90"
                    whileHover={{ scale: 1.08 }}
                    whileTap={{ scale: 0.92 }}
                    aria-label={showPass ? 'Hide password' : 'Show password'}
                  >
                    <AnimatePresence mode="wait" initial={false}>
                      {showPass ? (
                        <motion.span
                          key="hide"
                          initial={{ opacity: 0, rotate: -45 }}
                          animate={{ opacity: 1, rotate: 0 }}
                          exit={{ opacity: 0, rotate: 45 }}
                          transition={{ duration: 0.18 }}
                        >
                          <EyeOff className="h-4 w-4" />
                        </motion.span>
                      ) : (
                        <motion.span
                          key="show"
                          initial={{ opacity: 0, rotate: 45 }}
                          animate={{ opacity: 1, rotate: 0 }}
                          exit={{ opacity: 0, rotate: -45 }}
                          transition={{ duration: 0.18 }}
                        >
                          <Eye className="h-4 w-4" />
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </motion.button>
                </div>
                <AnimatePresence>
                  {capsOn && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.18 }}
                      className="text-[11px] text-amber-600 font-medium overflow-hidden"
                    >
                      ⚠ Caps Lock is on.
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>

              {/* Inline error */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0, marginTop: 0 }}
                    animate={{ opacity: 1, height: 'auto', marginTop: 4 }}
                    exit={{ opacity: 0, height: 0, marginTop: 0 }}
                    transition={{ duration: 0.22, ease: EASE_OUT_EXPO }}
                    className="rounded-xl border border-rose-200/70 bg-rose-50/80 backdrop-blur-sm px-3.5 py-2.5 text-[13px] text-rose-700 overflow-hidden"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit */}
              <motion.div whileHover={{ scale: loading ? 1 : 1.005 }} whileTap={{ scale: loading ? 1 : 0.985 }}>
                <Button
                  type="submit"
                  className="w-full h-11 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-blue-600 hover:from-violet-700 hover:via-indigo-700 hover:to-blue-700 text-white font-semibold tracking-tight shadow-[0_10px_30px_-10px_rgb(99,102,241,0.6)] hover:shadow-[0_14px_36px_-10px_rgb(99,102,241,0.7)] transition-all duration-300 ease-out disabled:opacity-60"
                  size="lg"
                  loading={loading}
                  disabled={!email || !password}
                >
                  Sign in
                  <motion.span
                    animate={{ x: loading ? 0 : [0, 3, 0] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
                  >
                    <ArrowRight className="h-4 w-4 ml-1" />
                  </motion.span>
                </Button>
              </motion.div>

              {/* Divider */}
              <div className="relative py-1">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-slate-200/70" />
                </div>
                <div className="relative flex justify-center text-[10px] uppercase tracking-[0.2em] font-semibold">
                  <span className="bg-white/80 backdrop-blur-md px-3 text-slate-400">or</span>
                </div>
              </div>

              {/* Google placeholder */}
              <motion.button
                type="button"
                disabled
                className="w-full h-11 rounded-xl border border-slate-200/80 bg-white/70 backdrop-blur-sm text-slate-700 text-[14px] font-medium flex items-center justify-center gap-2.5 hover:bg-white/90 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
                whileHover={{ scale: 1.005 }}
                whileTap={{ scale: 0.99 }}
                title="Coming soon"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Continue with Google
                <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold ml-auto">Soon</span>
              </motion.button>
            </form>

            <motion.p variants={fadeIn} className="text-center text-[13px] text-slate-500 mt-7">
              New here?{' '}
              <Link
                href="/auth/signup"
                className="text-indigo-600 font-semibold hover:text-indigo-800 transition-colors duration-200 inline-flex items-center gap-0.5 group"
              >
                Create an account
                <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
              </Link>
            </motion.p>
          </motion.div>

          {/* Trust footer */}
          <motion.div variants={fadeIn} className="flex items-center justify-center gap-1.5 mt-5 text-[11px] text-slate-400">
            <Lock className="h-3 w-3" />
            <span>Bank-grade encryption · Your data never leaves our database</span>
          </motion.div>
        </motion.div>
      </motion.section>
    </div>
  )
}

// ── Background layer (animated mesh + drifting orbs + dot grid) ──────────────
function BackgroundLayer({ reduced }: { reduced: boolean }) {
  return (
    <>
      {/* Drifting conic gradient (very subtle) */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.55]"
        style={{
          background:
            'conic-gradient(from 220deg at 30% 25%, rgba(139,92,246,0.18), rgba(99,102,241,0.10), rgba(59,130,246,0.14), rgba(139,92,246,0.18))',
          filter: 'blur(60px)',
        }}
        animate={reduced ? {} : { rotate: [0, 360] }}
        transition={{ duration: 60, repeat: Infinity, ease: 'linear' }}
      />

      {/* Floating orbs */}
      <FloatingOrb className="top-[8%] left-[10%] w-[380px] h-[380px]"  color="violet" delay={0}   reduced={reduced} />
      <FloatingOrb className="bottom-[12%] right-[14%] w-[460px] h-[460px]" color="indigo" delay={1.4} reduced={reduced} />
      <FloatingOrb className="top-[40%] right-[26%] w-[280px] h-[280px]"   color="blue"   delay={2.6} reduced={reduced} />

      {/* Subtle dot grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 1px 1px, rgba(99,102,241,0.18) 1px, transparent 0)',
          backgroundSize: '32px 32px',
          maskImage:
            'radial-gradient(ellipse at center, rgba(0,0,0,0.6), transparent 70%)',
          WebkitMaskImage:
            'radial-gradient(ellipse at center, rgba(0,0,0,0.6), transparent 70%)',
        }}
      />

      {/* Floating math symbols (decorative, very low opacity) */}
      {!reduced && (
        <>
          <FloatingSymbol char="∫" className="top-[18%] left-[42%]" delay={0} />
          <FloatingSymbol char="π" className="top-[68%] left-[18%]" delay={1.2} />
          <FloatingSymbol char="Σ" className="bottom-[22%] right-[40%]" delay={2.0} />
          <FloatingSymbol char="∂" className="top-[28%] right-[10%]" delay={0.6} />
        </>
      )}
    </>
  )
}

function FloatingOrb({
  className, color, delay, reduced,
}: {
  className: string
  color: 'violet' | 'indigo' | 'blue'
  delay: number
  reduced: boolean
}) {
  const fill = {
    violet: 'rgba(167, 139, 250, 0.32)',
    indigo: 'rgba(129, 140, 248, 0.28)',
    blue:   'rgba(96, 165, 250, 0.25)',
  }[color]
  return (
    <motion.div
      aria-hidden
      className={`pointer-events-none absolute rounded-full blur-3xl ${className}`}
      style={{ background: `radial-gradient(circle, ${fill} 0%, transparent 70%)` }}
      animate={
        reduced
          ? {}
          : {
              y: [0, -28, 0, 22, 0],
              x: [0, 18, 0, -16, 0],
              scale: [1, 1.05, 1, 0.97, 1],
            }
      }
      transition={{ duration: 14, delay, repeat: Infinity, ease: 'easeInOut' }}
    />
  )
}

function FloatingSymbol({ char, className, delay }: { char: string; className: string; delay: number }) {
  return (
    <motion.div
      aria-hidden
      className={`pointer-events-none absolute select-none text-7xl font-serif text-indigo-300/30 ${className}`}
      animate={{ y: [0, -14, 0, 10, 0], rotate: [0, 4, 0, -4, 0] }}
      transition={{ duration: 12, delay, repeat: Infinity, ease: 'easeInOut' }}
    >
      {char}
    </motion.div>
  )
}

// ── Student-facing benefits (replaces engineer-facing stat cards) ─────────────
// These speak to the student's experience, not the system's metrics. Every line
// is an answer to "what's in it for me as a JEE/NEET aspirant?"
const BENEFITS = [
  {
    label:   'Think it through',
    desc:    'Hints that guide, never spoil',
    icon:    <Lightbulb className="h-4 w-4" />,
    tone:    'violet' as const,
  },
  {
    label:   'Tutor for you',
    desc:    'Adapts to how you learn',
    icon:    <GraduationCap className="h-4 w-4" />,
    tone:    'indigo' as const,
  },
  {
    label:   'Catch mistakes',
    desc:    'Spot errors before exam day',
    icon:    <Target className="h-4 w-4" />,
    tone:    'blue' as const,
  },
]

function BenefitCard({
  label, desc, icon, tone,
}: {
  label: string; desc: string; icon: React.ReactNode; tone: 'violet' | 'indigo' | 'blue'
}) {
  const accentBg = {
    violet: 'bg-violet-100/70 text-violet-700',
    indigo: 'bg-indigo-100/70 text-indigo-700',
    blue:   'bg-blue-100/70   text-blue-700',
  }[tone]
  // Tilt-on-hover micro-interaction — subtle 3D feel without a perf hit.
  return (
    <motion.div
      whileHover={{ y: -4, rotateX: 4, rotateY: -4, scale: 1.03 }}
      transition={{ duration: 0.28, ease: EASE_OUT_EXPO }}
      style={{ transformPerspective: 800 }}
      className="rounded-2xl border border-white/60 bg-white/70 backdrop-blur-md p-4 shadow-[0_8px_24px_-8px_rgb(99,102,241,0.12)] hover:shadow-[0_14px_30px_-12px_rgb(99,102,241,0.22)]"
    >
      <motion.div
        className={`inline-flex items-center justify-center w-8 h-8 rounded-lg ${accentBg} mb-2.5`}
        whileHover={{ rotate: [0, -8, 8, 0] }}
        transition={{ duration: 0.5 }}
      >
        {icon}
      </motion.div>
      <div className="text-sm font-bold tracking-tight text-slate-900 leading-tight">{label}</div>
      <div className="text-[11.5px] text-slate-500 font-medium mt-1 leading-snug">{desc}</div>
    </motion.div>
  )
}

// ── Live demo chat preview (animated typewriter Socratic exchange) ────────────
// Shows the student what the tutor experience actually feels like, instead of
// abstract stats. The AI bubble types out a Socratic question character-by-character;
// a pulsing emerald dot signals "live."
function ChatPreview() {
  return (
    <div className="rounded-2xl border border-white/70 bg-white/70 backdrop-blur-md p-4 shadow-[0_10px_30px_-10px_rgb(99,102,241,0.18)]">
      <div className="flex items-center gap-2 mb-3">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 animate-ping" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span className="text-[10px] uppercase tracking-[0.18em] text-slate-500 font-semibold">
          Live tutor
        </span>
        <span className="ml-auto text-[10px] text-slate-400 font-medium">Socratic mode</span>
      </div>

      {/* Student bubble (right-aligned) */}
      <motion.div
        initial={{ opacity: 0, x: 16, scale: 0.95 }}
        animate={{ opacity: 1, x: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: EASE_OUT_EXPO, delay: 0.6 }}
        className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm border border-indigo-100 bg-gradient-to-br from-indigo-50 to-violet-50/80 px-3.5 py-2.5 mb-2"
      >
        <p className="text-[13px] text-slate-700 leading-snug">
          I&apos;m stuck on the integral of <span className="font-mono text-indigo-700">x²·eˣ</span>
        </p>
      </motion.div>

      {/* AI bubble (left-aligned) with typewriter */}
      <motion.div
        initial={{ opacity: 0, x: -16, scale: 0.95 }}
        animate={{ opacity: 1, x: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: EASE_OUT_EXPO, delay: 1.4 }}
        className="mr-auto max-w-[90%] rounded-2xl rounded-tl-sm border border-slate-100 bg-white/90 px-3.5 py-2.5"
      >
        <p className="text-[13px] text-slate-700 leading-snug">
          <Typewriter
            text="What does integration by parts suggest you pick as u and dv?"
            startDelayMs={1700}
            speedMs={32}
          />
        </p>
      </motion.div>
    </div>
  )
}

// Typewriter — characters appear one-by-one with a soft caret. Pure framer-motion
// + useEffect, no extra deps. Caret blinks while typing, fades after completion.
function Typewriter({
  text, startDelayMs = 0, speedMs = 30,
}: { text: string; startDelayMs?: number; speedMs?: number }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const startTimer = setTimeout(() => {
      const tick = setInterval(() => {
        setShown((s) => {
          if (s >= text.length) {
            clearInterval(tick)
            return s
          }
          return s + 1
        })
      }, speedMs)
      return () => clearInterval(tick)
    }, startDelayMs)
    return () => clearTimeout(startTimer)
  }, [text, speedMs, startDelayMs])

  const isDone = shown >= text.length
  return (
    <span>
      {text.slice(0, shown)}
      <motion.span
        aria-hidden
        className="inline-block w-[2px] align-baseline ml-0.5"
        style={{ height: '1em', background: '#6366F1' }}
        animate={{ opacity: isDone ? 0 : [1, 0, 1] }}
        transition={{ duration: 0.7, repeat: isDone ? 0 : Infinity }}
      />
    </span>
  )
}

// ── Sparkle emit (fires once on mount, around the "think" underline) ─────────
// Six small sparkles spawn from a central point and fly outward at evenly
// spaced angles, fading as they travel. The whole burst completes in ~1.4s
// and never repeats — it's a one-shot reward visual right after the headline
// underline finishes drawing.
function SparkleEmit() {
  const reduced = useReducedMotion()
  if (reduced) return null
  const SPARKS = 6
  return (
    <span aria-hidden className="pointer-events-none absolute inset-0 -m-4">
      {Array.from({ length: SPARKS }).map((_, i) => {
        const angle = (i / SPARKS) * Math.PI * 2
        const distance = 28 + (i % 2 === 0 ? 6 : -4)
        const dx = Math.cos(angle) * distance
        const dy = Math.sin(angle) * distance
        return (
          <motion.span
            key={i}
            className="absolute left-1/2 top-1/2"
            initial={{ opacity: 0, x: 0, y: 0, scale: 0 }}
            animate={{
              opacity: [0, 1, 0],
              x: [0, dx],
              y: [0, dy],
              scale: [0, 1, 0.6],
            }}
            transition={{ duration: 1.4, delay: 1.1 + i * 0.04, ease: EASE_OUT_EXPO }}
          >
            <Sparkles
              className="h-2.5 w-2.5"
              style={{ color: ['#A78BFA', '#818CF8', '#60A5FA'][i % 3] }}
            />
          </motion.span>
        )
      })}
    </span>
  )
}

function SubjectPill({
  icon, label, tone,
}: { icon: React.ReactNode; label: string; tone: 'indigo' | 'emerald' | 'violet' }) {
  const cls = {
    indigo:  'border-indigo-200/70 bg-indigo-50/70 text-indigo-700',
    emerald: 'border-emerald-200/70 bg-emerald-50/70 text-emerald-700',
    violet:  'border-violet-200/70 bg-violet-50/70 text-violet-700',
  }[tone]
  return (
    <motion.span
      whileHover={{ y: -1, scale: 1.04 }}
      transition={{ duration: 0.2, ease: EASE_OUT_EXPO }}
      className={`inline-flex items-center gap-1.5 rounded-full border backdrop-blur-md px-2.5 py-1 text-[11px] font-semibold ${cls}`}
    >
      {icon}
      {label}
    </motion.span>
  )
}
