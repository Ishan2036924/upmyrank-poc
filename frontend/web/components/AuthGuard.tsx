'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'

/**
 * Wrap any page that requires authentication.
 * Redirects to /auth/login if no token found after loading.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !token) {
      router.replace('/auth/login')
    }
  }, [token, isLoading, router])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 animate-pulse" />
          <p className="text-sm text-slate-400">Loading…</p>
        </div>
      </div>
    )
  }

  if (!token) return null

  return <>{children}</>
}
