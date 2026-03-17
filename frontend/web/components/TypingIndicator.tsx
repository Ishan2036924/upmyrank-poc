'use client'

export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 mb-4">
      {/* AI avatar */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-green-900 text-green-400 flex items-center justify-center text-xs font-bold">
        AI
      </div>
      <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex gap-1.5 items-center h-5">
          <span className="typing-dot w-2 h-2 rounded-full bg-gray-400 inline-block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-gray-400 inline-block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-gray-400 inline-block" />
        </div>
      </div>
    </div>
  )
}
