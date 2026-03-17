'use client'

import { forwardRef, useState, useRef, KeyboardEvent } from 'react'
import { Send } from 'lucide-react'

interface Props {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

const ChatInput = forwardRef<HTMLTextAreaElement, Props>(
  function ChatInput({ onSend, disabled, placeholder }, forwardedRef) {
    const [value, setValue] = useState('')
    const internalRef = useRef<HTMLTextAreaElement>(null)
    // Use forwarded ref if provided, otherwise fall back to internal
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
      <div className="border-t border-gray-800 bg-gray-950 px-4 py-4">
        <div className="flex items-end gap-3 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3">
          <textarea
            ref={ref}
            rows={1}
            value={value}
            onChange={(e) => { setValue(e.target.value); handleInput() }}
            onKeyDown={handleKey}
            disabled={disabled}
            placeholder={placeholder ?? 'Type your response or ask a question…'}
            className="flex-1 bg-transparent text-sm text-white placeholder-gray-500 resize-none outline-none leading-relaxed"
            style={{ maxHeight: 160 }}
          />
          <button
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            className="flex-shrink-0 w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
          >
            <Send className="h-4 w-4 text-white" />
          </button>
        </div>
        <div className="flex gap-4 mt-2 px-1 text-xs text-gray-600">
          <span>↵ Send  ·  Shift+↵ New line</span>
          <span>Supports LaTeX: $f(x)$</span>
        </div>
      </div>
    )
  }
)

ChatInput.displayName = 'ChatInput'

export default ChatInput
