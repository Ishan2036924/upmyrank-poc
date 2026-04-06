'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)

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
      // Fetch name from /auth/me
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

      // Check onboarding status — redirect to /onboarding if not yet done
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
      try {
        const parsed = JSON.parse(msg)
        setError(parsed.detail ?? msg)
      } catch {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        {/* Logo / brand */}
        <div className="text-center mb-10">
          <div className="inline-flex w-16 h-16 rounded-3xl bg-gradient-to-br from-violet-500 to-indigo-600 items-center justify-center mb-5 shadow-xl shadow-indigo-200/60 ring-4 ring-white">
            <span className="text-3xl">🎓</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Welcome back</h1>
          <p className="text-slate-500 text-sm mt-1">Sign in to continue your JEE/NEET prep</p>
        </div>

        {/* Card */}
        <div className="bg-white/80 backdrop-blur-xl rounded-3xl border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.06)] p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                placeholder="you@example.com"
                className="w-full rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-sm text-slate-800 placeholder-slate-400 outline-none transition-all duration-300 focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading}
                placeholder="••••••••"
                className="w-full rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-sm text-slate-800 placeholder-slate-400 outline-none transition-all duration-300 focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-300 disabled:opacity-50"
              />
            </div>

            {error && (
              <div className="rounded-2xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-600">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full rounded-2xl bg-slate-900 hover:bg-indigo-600 text-white font-semibold py-3.5 text-sm transition-all duration-300 ease-out hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-slate-900/20 hover:shadow-indigo-500/30"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            New student?{' '}
            <Link
              href="/auth/signup"
              className="text-indigo-600 font-medium hover:text-indigo-700 transition-colors"
            >
              Create account
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
