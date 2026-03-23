'use client'

import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import type { Components } from 'react-markdown'

/**
 * Normalise LLM math delimiters to standard $...$ / $$...$$ form.
 * Handles: \(...\), \[...\], and stray bare-backslash patterns.
 */
function fixLatex(text: string): string {
  // \(...\) → $...$
  text = text.replace(/\\\(\s*/g, '$')
  text = text.replace(/\s*\\\)/g, '$')
  // \[...\] → $$...$$
  text = text.replace(/\\\[\s*/g, '$$')
  text = text.replace(/\s*\\\]/g, '$$')
  // Collapse accidental $$$  →  $$
  text = text.replace(/\$\$\$/g, '$$')
  return text
}

const MD_COMPONENTS: Components = {
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
  ),
  h1: ({ children }) => (
    <h1 className="text-base font-bold mt-3 mb-1">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-sm font-bold mt-2 mb-1">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold mt-2 mb-0.5">{children}</h3>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  code: ({ className, children }) => {
    const isBlock = String(className ?? '').startsWith('language-')
    return isBlock ? (
      <code className="block bg-slate-100 text-slate-700 rounded-xl px-3 py-2 text-xs font-mono my-2 overflow-x-auto whitespace-pre">
        {children}
      </code>
    ) : (
      <code className="bg-slate-100 text-slate-700 rounded px-1 py-0.5 text-xs font-mono">
        {children}
      </code>
    )
  },
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-slate-300 pl-3 my-2 text-slate-500 italic">
      {children}
    </blockquote>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  hr: () => <hr className="border-slate-200 my-3" />,
}

interface MathTextProps {
  children: string
  className?: string
}

/**
 * Renders a string that may contain:
 *   • Markdown (headers, lists, bold, code, etc.)
 *   • LaTeX inline math:  $...$  or \(...\)
 *   • LaTeX block math:  $$...$$  or \[...\]
 *
 * The fixLatex() pass normalises the LLM's varied delimiter styles to the
 * standard forms that remark-math / KaTeX expect.
 *
 * katex/dist/katex.min.css is imported globally in app/globals.css.
 */
export default function MathText({ children, className }: MathTextProps) {
  const normalized = fixLatex(children)
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[[rehypeKatex, { output: 'html' }]]}
        components={MD_COMPONENTS}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  )
}
