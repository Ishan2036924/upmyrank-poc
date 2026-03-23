import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'UpMyRank — AI Tutor',
  description: 'AI-powered JEE/NEET tutoring · NCERT Physics Class 11 & 12',
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
        {children}
      </body>
    </html>
  )
}
