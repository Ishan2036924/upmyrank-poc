import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { AuthProvider } from '@/lib/auth'
import QuickDoubtFAB from '@/components/QuickDoubtFAB'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'UpMyRank — AI Tutor',
  description: 'AI-powered JEE/NEET tutoring · Physics, Chemistry & Maths · NCERT Class 11 & 12',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="h-full">
      <body className={`${inter.className} h-full text-slate-900 antialiased`}>
        <div className="mesh-bg" />
        <AuthProvider>
          <TooltipProvider delayDuration={200}>
            {children}
            {/* FAB rendered globally — hides itself on /doubt, /auth, /onboarding */}
            <QuickDoubtFAB />
          </TooltipProvider>
          <Toaster />
        </AuthProvider>
      </body>
    </html>
  )
}
