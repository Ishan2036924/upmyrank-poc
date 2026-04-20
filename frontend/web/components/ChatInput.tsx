'use client'

import { forwardRef, useState, useRef, KeyboardEvent } from 'react'
import { Send, ImagePlus, X } from 'lucide-react'

interface Props {
  onSend: (text: string, imageUrl?: string) => void
  disabled?: boolean
  placeholder?: string
}

const ChatInput = forwardRef<HTMLTextAreaElement, Props>(
  function ChatInput({ onSend, disabled, placeholder }, forwardedRef) {
    const [value,        setValue]        = useState('')
    const [imageFile,    setImageFile]    = useState<File | null>(null)
    const [imagePreview, setImagePreview] = useState<string | null>(null)
    const [uploading,    setUploading]    = useState(false)
    const [uploadError,  setUploadError]  = useState<string | null>(null)

    const internalRef = useRef<HTMLTextAreaElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const ref = (forwardedRef as React.RefObject<HTMLTextAreaElement>) || internalRef

    // FIX #3 (2026-04-19): synchronous re-entry guard. Enter-key + click or
    // rapid double-click previously slipped two handleSend() calls through
    // because setUploading(true) is async (state update doesn't fire until
    // the next render). Using a ref gives us a truly synchronous lock.
    const inFlightRef = useRef(false)

    const handleSend = async () => {
      if (inFlightRef.current) return
      const trimmed = value.trim()
      if ((!trimmed && !imageFile) || disabled || uploading) return

      inFlightRef.current = true
      setUploading(true)
      setUploadError(null)
      let imageUrl: string | undefined

      if (imageFile) {
        try {
          imageUrl = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = (e) => {
              const result = e.target?.result
              if (typeof result === 'string') resolve(result)
              else reject(new Error('Failed to read image'))
            }
            reader.onerror = () => reject(new Error('Failed to read image'))
            reader.readAsDataURL(imageFile)
          })
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err)
          setUploadError(`Image read failed: ${msg}`)
          setUploading(false)
          inFlightRef.current = false
          return
        }
      }

      // Fire and reset
      onSend(trimmed, imageUrl)
      setValue('')
      setImageFile(null)
      setImagePreview(null)
      setUploading(false)
      inFlightRef.current = false
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

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      if (!file.type.startsWith('image/')) {
        setUploadError('Only image files are supported')
        return
      }
      setImageFile(file)
      setUploadError(null)
      const reader = new FileReader()
      reader.onload = (ev) => setImagePreview(ev.target?.result as string)
      reader.readAsDataURL(file)
      // Reset input so same file can be re-selected
      e.target.value = ''
    }

    const removeImage = () => {
      setImageFile(null)
      setImagePreview(null)
      setUploadError(null)
    }

    const canSend = !disabled && !uploading && (!!value.trim() || !!imageFile)

    return (
      <div className="px-5 pb-5 pt-2 flex-shrink-0">
        {/* Image preview strip */}
        {imagePreview && (
          <div className="mb-3 flex items-start gap-3">
            <div className="relative inline-block">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imagePreview}
                alt="Attached image"
                className="max-h-[120px] rounded-2xl border border-slate-200 shadow-sm object-contain bg-white/80"
              />
              <button
                onClick={removeImage}
                className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-slate-800 text-white flex items-center justify-center hover:bg-red-500 transition-colors shadow-md"
                title="Remove image"
              >
                <X style={{ width: 12, height: 12 }} />
              </button>
            </div>
            <div className="flex flex-col justify-end pb-1">
              <span className="text-xs text-slate-500 font-medium">{imageFile?.name}</span>
              <span className="text-[11px] text-slate-400 mt-0.5">
                AI will extract the question from this image
              </span>
            </div>
          </div>
        )}

        {/* Upload error */}
        {uploadError && (
          <div className="mb-2 rounded-2xl bg-red-50 border border-red-100 px-4 py-2 text-xs text-red-600">
            {uploadError}
          </div>
        )}

        {/* Floating pill — glassmorphic */}
        <div className="flex items-end gap-3 bg-white/90 backdrop-blur-sm border border-slate-200/70 rounded-3xl px-4 py-3 shadow-[0_8px_30px_rgb(0,0,0,0.06)] transition-all duration-300 ease-out focus-within:ring-2 focus-within:ring-indigo-500/30 focus-within:border-indigo-200/80 focus-within:shadow-[0_8px_30px_rgb(99,102,241,0.10)]">
          {/* Image attach button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}
            className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 transition-all duration-300 ease-out active:scale-90 mb-0.5 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Attach image"
            type="button"
          >
            <ImagePlus style={{ width: 16, height: 16 }} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
          />

          <textarea
            ref={ref}
            rows={1}
            value={value}
            onChange={(e) => { setValue(e.target.value); handleInput() }}
            onKeyDown={handleKey}
            disabled={disabled || uploading}
            placeholder={
              uploading
                ? 'Uploading image…'
                : placeholder ?? 'Ask a Physics question or attach an image…'
            }
            className="flex-1 bg-transparent text-sm text-slate-800 placeholder-slate-400 resize-none outline-none leading-relaxed py-1 disabled:opacity-60"
            style={{ maxHeight: 160, fontSize: 16 }}
          />

          {/* Send button */}
          <button
            onClick={handleSend}
            disabled={!canSend}
            className={`flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 ease-out mb-0.5 ${
              canSend
                ? 'bg-slate-900 hover:bg-indigo-600 hover:scale-110 active:scale-90 shadow-md shadow-slate-900/20 hover:shadow-indigo-500/30 cursor-pointer'
                : 'bg-slate-200 opacity-50 cursor-not-allowed'
            }`}
          >
            <Send style={{ width: 15, height: 15 }} className="text-white translate-x-0.5" />
          </button>
        </div>

        {/* Hint strip */}
        <div className="flex gap-4 mt-2 px-4 text-xs text-slate-400">
          <span>↵ Send · Shift+↵ New line</span>
          <span>📷 Attach image · Supports LaTeX: $f(x)$</span>
        </div>
      </div>
    )
  }
)

ChatInput.displayName = 'ChatInput'

export default ChatInput
