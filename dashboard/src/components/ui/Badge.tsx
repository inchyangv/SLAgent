import React from 'react'

export type BadgeVariant =
  | 'pass'
  | 'fail'
  | 'partial'
  | 'full'
  | 'info'
  | 'warning'
  | 'neutral'
  | 'success'
  | 'error'

const variantStyles: Record<BadgeVariant, string> = {
  pass: 'bg-green-950 text-green-400 border border-green-900',
  fail: 'bg-red-950 text-red-400 border border-red-900',
  partial: 'bg-orange-950 text-orange-400 border border-orange-900',
  full: 'bg-blue-950 text-blue-400 border border-blue-900',
  info: 'bg-zinc-900 text-zinc-400 border border-zinc-800',
  warning: 'bg-amber-950 text-amber-400 border border-amber-900',
  neutral: 'bg-zinc-900 text-zinc-500 border border-zinc-800',
  success: 'bg-green-950 text-green-400 border border-green-900',
  error: 'bg-red-950 text-red-400 border border-red-900',
}

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
}

export function Badge({ variant = 'neutral', children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium font-mono badge-transition ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  )
}

export function slaStatusVariant(status: string | undefined): BadgeVariant {
  if (status === 'pass') return 'pass'
  if (status === 'fail') return 'fail'
  if (status === 'partial') return 'partial'
  return 'neutral'
}
