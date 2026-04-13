'use client'

/**
 * QuickDoubtFAB — Floating action button + bottom-sheet doubt entry.
 *
 * Behavior:
 *   1. Shows a 56px circle FAB at bottom-right on every screen
 *      except when the doubt chat page is active.
 *   2. "Quick Doubt" label pill appears on first render, fades after 3s.
 *   3. Tap → bottom sheet rises with a large text input.
 *   4. Student types their question → Send opens /doubt with the question
 *      pre-filled as a URL param so the doubt page auto-submits it.
 *   5. Subject is auto-detected server-side (_classify_subject runs normally).
 *      If no question typed, the sheet just navigates to /doubt.
 *
 * NOT shown on /doubt (the chat page itself).
 */

import { useEffect, useRef, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle, X, ArrowRight, Sparkles } from 'lucide-react'

export default function QuickDoubtFAB() {
  const pathname = usePathname()
  const router   = useRouter()

  const [sheetOpen,   setSheetOpen]   = useState(false)
  const [labelVisible, setLabelVisible] = useState(true)
  const [question,    setQuestion]    = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Hide label after 3 seconds
  useEffect(() => {
    const t = setTimeout(() => setLabelVisible(false), 3000)
    return () => clearTimeout(t)
  }, [])

  // Focus textarea when sheet opens
  useEffect(() => {
    if (sheetOpen) {
      setTimeout(() => textareaRef.current?.focus(), 120)
    } else {
      setQuestion('')
    }
  }, [sheetOpen])

  // Auto-resize textarea
  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  const handleSend = () => {
    const q = question.trim()
    if (q) {
      // Pass question as URL param — doubt page reads it and auto-submits
      const params = new URLSearchParams({ q })
      router.push(`/doubt?${params.toString()}`)
    } else {
      router.push('/doubt')
    }
    setSheetOpen(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
    if (e.key === 'Escape') {
      setSheetOpen(false)
    }
  }

  // Don't render on the doubt page itself
  if (pathname.startsWith('/doubt')) return null
  // Don't render on auth or onboarding pages
  if (pathname.startsWith('/auth') || pathname.startsWith('/onboarding')) return null

  return (
    <>
      {/* ── FAB ──────────────────────────────────────────────────────────────── */}
      <div className="fixed bottom-6 right-4 z-50 flex items-center gap-2 pointer-events-none">
        {/* "Quick Doubt" label pill */}
        <AnimatePresence>
          {labelVisible && !sheetOpen && (
            <motion.div
              initial={{ opacity: 0, x: 10, scale: 0.9 }}
              animate={{ opacity: 1, x: 0,  scale: 1   }}
              exit={{   opacity: 0, x: 6,  scale: 0.95 }}
              transition={{ duration: 0.25 }}
              className="bg-slate-900/90 backdrop-blur-sm text-white text-xs font-semibold px-3 py-1.5 rounded-full shadow-lg pointer-events-none whitespace-nowrap"
            >
              Quick Doubt
            </motion.div>
          )}
        </AnimatePresence>

        {/* The circle button */}
        <motion.button
          onClick={() => setSheetOpen(true)}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.93 }}
          className="w-14 h-14 rounded-full bg-slate-900 text-white flex items-center justify-center shadow-[0_8px_30px_rgba(0,0,0,0.22)] hover:bg-indigo-700 transition-colors duration-300 pointer-events-auto"
          aria-label="Quick Doubt"
        >
          <MessageCircle style={{ width: 22, height: 22 }} />
        </motion.button>
      </div>

      {/* ── Bottom sheet + backdrop ──────────────────────────────────────────── */}
      <AnimatePresence>
        {sheetOpen && (
          <motion.div
            key="sheet-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[60] flex flex-col justify-end"
          >
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-black/25 backdrop-blur-[2px]"
              onClick={() => setSheetOpen(false)}
            />

            {/* Sheet */}
            <motion.div
              key="sheet"
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
              className="relative bg-white/95 backdrop-blur-xl rounded-t-3xl shadow-2xl px-5 pt-5 pb-8 z-10"
              // Prevent sheet from going under keyboard on mobile
              style={{ paddingBottom: 'max(32px, env(safe-area-inset-bottom, 32px))' }}
            >
              {/* Drag handle */}
              <div className="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-5" />

              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-indigo-500" />
                  <span className="text-sm font-semibold text-slate-800">Quick Doubt</span>
                  <span className="text-xs text-slate-400">— AI will detect the subject</span>
                </div>
                <button
                  onClick={() => setSheetOpen(false)}
                  className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 hover:text-slate-800 hover:bg-slate-200 transition-colors"
                >
                  <X style={{ width: 13, height: 13 }} />
                </button>
              </div>

              {/* Input area */}
              <div className="relative bg-slate-50 border border-slate-200/80 rounded-2xl px-4 py-3 focus-within:ring-2 focus-within:ring-indigo-400/40 focus-within:border-indigo-300 transition-all duration-200">
                <textarea
                  ref={textareaRef}
                  rows={3}
                  value={question}
                  onChange={(e) => { setQuestion(e.target.value); handleInput() }}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your Physics, Chemistry, or Maths doubt…"
                  className="w-full bg-transparent text-sm text-slate-800 placeholder-slate-400 resize-none outline-none leading-relaxed"
                  // font-size 16px prevents iOS auto-zoom on focus
                  style={{ fontSize: 16, maxHeight: 160 }}
                />
              </div>

              <div className="flex items-center justify-between mt-3">
                <span className="text-xs text-slate-400">↵ Send · Shift+↵ New line · Esc Close</span>
                <motion.button
                  onClick={handleSend}
                  whileTap={{ scale: 0.94 }}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-200 ${
                    question.trim()
                      ? 'bg-slate-900 text-white hover:bg-indigo-700 shadow-md shadow-slate-900/20'
                      : 'bg-slate-100 text-slate-400 cursor-default'
                  }`}
                >
                  {question.trim() ? 'Ask' : 'Open chat'}
                  <ArrowRight style={{ width: 14, height: 14 }} />
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
