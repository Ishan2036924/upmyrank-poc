'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Sparkles, Mail, ArrowLeft, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function ForgotPasswordPage() {
  const [email,     setEmail]     = useState('')
  const [sent,      setSent]      = useState(false)
  const [loading,   setLoading]   = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    // Scaffolded — backend endpoint not yet wired.
    await new Promise((r) => setTimeout(r, 600))
    setLoading(false)
    setSent(true)
    toast.info('Email delivery is coming soon', {
      description: 'Until then, contact support to reset your password.',
    })
  }

  return (
    <div className="min-h-[100dvh] flex items-center justify-center p-6">
      <Card className="w-full max-w-md shadow-soft">
        <CardHeader>
          <Link href="/auth/login" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mb-3">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to sign in
          </Link>
          <div className="flex items-center gap-2 mb-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-indigo-600 shadow-soft">
              <Sparkles className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-sm font-bold text-foreground">UpMyRank</span>
          </div>
          <CardTitle>Reset your password</CardTitle>
          <CardDescription>
            Enter your email and we&apos;ll send you a reset link.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sent ? (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <CheckCircle2 className="h-6 w-6 text-success" />
              </div>
              <div>
                <div className="text-sm font-medium text-foreground">Request received</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Email delivery is coming soon. Contact{' '}
                  <a href="mailto:support@upmyrank.com" className="text-primary hover:underline">support@upmyrank.com</a>{' '}
                  to reset your password for now.
                </p>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link href="/auth/login">Back to sign in</Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="pl-9" placeholder="you@example.com" />
                </div>
              </div>
              <Button type="submit" className="w-full" loading={loading} disabled={!email}>
                Send reset link
              </Button>
              <p className="text-[11px] text-center text-muted-foreground">
                Remembered it?{' '}
                <Link href="/auth/login" className="text-primary hover:underline">Sign in</Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
