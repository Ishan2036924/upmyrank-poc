/**
 * cn — merge Tailwind class names safely.
 *
 * Combines clsx (conditional classes) with tailwind-merge (dedupes
 * conflicting utilities, e.g. "px-2 px-4" → "px-4"). Every shadcn/ui
 * primitive in components/ui/ uses this helper.
 */
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/**
 * Format a number with locale-aware thousand separators.
 * Used by admin dashboard + stat cards.
 */
export function formatNumber(value: number | null | undefined, fractionDigits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

/**
 * Format a percentage (0–1 or 0–100) as a display string.
 */
export function formatPercent(value: number | null | undefined, fractionDigits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const pct = value > 1 ? value : value * 100
  return `${pct.toFixed(fractionDigits)}%`
}

/**
 * Get initials from a name for Avatar fallback ("Rahul Kumar" → "RK").
 */
export function getInitials(name: string | null | undefined): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}
