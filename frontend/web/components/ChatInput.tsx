'use client'

import { forwardRef, useState, useRef, KeyboardEvent } from 'react'
import { Send, Plus } from 'lucide-react'

interface Props {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

const ChatInput = forwardRef<HTMLTextAreaElement, Props>(
  function ChatInput({ onSend, disabled, placeholder }, forwardedRef) {
    const [value, setValue] = useState('')
    const internalRef = useRef<HTMLTextAreaElement>(null)
    const ref = (forwardedRef as React.RefObject<HTMLTextAreaElement>) || internalRef

    const handleSend = () => {
      const trimmed = value.trim()
      if (!trimmed || disabled) return
      onSend(trimmed)
      setValue('')
      if (ref.current) ref.current.style.height = 'auto'
    }

    const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    }

    const handleInput = () => {
      if (!ref.current) return
      ref.current.style.height = 'auto'
      ref.current.style.height = Math.min(ref.current.scrollHeight, 160) + 'px'
    }

    return (
      <div className="px-6 pb-6 pt-3 flex-shrink-0">
        {/* Floating pill container */}
        <div className="flex items-end gap-3 bg-white/90 backdrop-blur-sm border border-slate-200/80 rounded-3xl px-4 py-3 shadow-lg shadow-slate-200/60">
          {/* Left attach button */}
          <button
            className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors mb-0.5"
            title="Attach"
            type="button"
          >
            <Plus style={{ width: 16, height: 16 }} />
          </button>

          <textarea
            ref={ref}
            rows={1}
            value={value}
            onChange={(e) => { setValue(e.target.value); handleInput() }}
            onKeyDown={handleKey}
            disabled={disabled}
            placeholder={placeholder ?? 'Type your response or ask a question…'}
            className="flex-1 bg-transparent text-sm text-slate-800 placeholder-slate-400 resize-none outline-none leading-relaxed py-1"
            style={{ maxHeight: 160 }}
          />

          {/* Right send button — dark circle */}
          <button
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            className="flex-shrink-0 w-9 h-9 rounded-full bg-slate-900 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-all shadow-md shadow-slate-900/20 mb-0.5"
          >
            <Send style={{ width: 15, height: 15 }} className="text-white translate-x-0.5" />
          </button>
        </div>

        {/* Help text */}
        <div className="flex gap-4 mt-2 px-4 text-xs text-slate-400">
          <span>↵ Send · Shift+↵ New line</span>
          <span>Supports LaTeX: $f(x)$</span>
        </div>
      </div>
    )
  }
)

ChatInput.displayName = 'ChatInput'

export default ChatInput
