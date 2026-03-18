import React from 'react'

interface StatCardProps {
  label: string
  value: string | number | React.ReactNode
  sub?: string
  variant?: 'default' | 'success' | 'error' | 'warning' | 'accent'
  className?: string
}

const variantColor: Record<string, string> = {
  default: 'var(--color-text-primary)',
  success: 'var(--color-success)',
  error: 'var(--color-error)',
  warning: 'var(--color-warning)',
  accent: 'var(--color-accent)',
}

export function StatCard({
  label,
  value,
  sub,
  variant = 'default',
  className = '',
}: StatCardProps) {
  return (
    <div
      className={`rounded-md p-3 border ${className}`}
      style={{
        background: 'var(--color-bg-elevated)',
        borderColor: 'var(--color-border)',
      }}
    >
      <div
        className="text-xs mb-1 font-medium uppercase tracking-wide"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </div>
      <div
        className="text-2xl font-bold font-mono leading-none"
        style={{ color: variantColor[variant] }}
      >
        {value}
      </div>
      {sub && (
        <div
          className="text-xs mt-1"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {sub}
        </div>
      )}
    </div>
  )
}
