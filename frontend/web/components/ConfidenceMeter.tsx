'use client'

import { motion } from 'framer-motion'

export type ConfidenceLevel = 'low' | 'medium' | 'high'

interface Props {
  onSelect: (level: ConfidenceLevel) => void
}

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1]

const OPTIONS: {
  level: ConfidenceLevel
  emoji: string
  label: string
  desc: string
  cls: string
  labelCls: string
  descCls: string
}[] = [
  {
    level:    'low',
    emoji:    '🔴',
    label:    'Taking a guess',
    desc:     'Not very sure',
    cls:      'hover:bg-rose-50 hover:border-rose-200 hover:shadow-rose-100/60',
    labelCls: 'group-hover:text-rose-700',
    descCls:  'group-hover:text-rose-400',
  },
  {
    level:    'medium',
    emoji:    '🟡',
    label:    'Somewhat sure',
    desc:     "Think I'm right",
    cls:      'hover:bg-amber-50 hover:border-amber-200 hover:shadow-amber-100/60',
    labelCls: 'group-hover:text-amber-700',
    descCls:  'group-hover:text-amber-400',
  },
  {
    level:    'high',
    emoji:    '🟢',
    label:    '100% Confident',
    desc:     'Definitely correct',
    cls:      'hover:bg-emerald-50 hover:border-emerald-200 hover:shadow-emerald-100/60',
    labelCls: 'group-hover:text-emerald-700',
    descCls:  'group-hover:text-emerald-400',
  },
]

export default function ConfidenceMeter({ onSelect }: Props) {
  return (
    <motion.div
      key="confidence-meter"
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ opacity: 1, scale: 1,    y: 0  }}
      exit={{    opacity: 0, scale: 0.95, y: 6  }}
      transition={{ duration: 0.28, ease: EASE }}
      className="mx-5 mb-5"
    >
      {/* Glassmorphic card */}
      <div className="bg-white/90 backdrop-blur-xl border border-white/60 rounded-3xl shadow-2xl shadow-slate-200/60 p-6">

        {/* Header */}
        <div className="text-center mb-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-widest">
            Before I reveal the solution…
          </p>
          <p className="text-sm font-semibold text-slate-800 mt-1.5">
            How sure are you about this answer?
          </p>
        </div>

        {/* Three confidence buttons */}
        <div className="grid grid-cols-3 gap-3">
          {OPTIONS.map((opt) => (
            <motion.button
              key={opt.level}
              onClick={() => onSelect(opt.level)}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.93 }}
              transition={{ duration: 0.2, ease: EASE }}
              className={`group flex flex-col items-center gap-2 rounded-2xl border border-slate-100 bg-white/80 px-3 py-4 text-center shadow-sm transition-all duration-300 ease-out hover:shadow-md ${opt.cls}`}
            >
              <span className="text-2xl leading-none">{opt.emoji}</span>
              <span className={`text-xs font-semibold text-slate-700 transition-colors duration-200 ${opt.labelCls}`}>
                {opt.label}
              </span>
              <span className={`text-[10px] text-slate-400 leading-tight transition-colors duration-200 ${opt.descCls}`}>
                {opt.desc}
              </span>
            </motion.button>
          ))}
        </div>

        {/* Subtle footer note */}
        <p className="text-center text-[10px] text-slate-300 mt-4">
          Your answer + confidence will be logged to your knowledge genome
        </p>
      </div>
    </motion.div>
  )
}
