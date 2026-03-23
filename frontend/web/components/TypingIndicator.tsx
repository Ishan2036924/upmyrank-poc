'use client'

export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white flex items-center justify-center text-[10px] font-bold shadow-md shadow-indigo-200">
        AI
      </div>
      <div className="bg-white rounded-3xl rounded-bl-lg px-5 py-3.5 shadow-sm shadow-slate-200/80 border border-slate-100">
        <div className="flex gap-1.5 items-center h-5">
          <span className="typing-dot w-2 h-2 rounded-full bg-slate-300 inline-block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-slate-300 inline-block" />
          <span className="typing-dot w-2 h-2 rounded-full bg-slate-300 inline-block" />
        </div>
      </div>
    </div>
  )
}
