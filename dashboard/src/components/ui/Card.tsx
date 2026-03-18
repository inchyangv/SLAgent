import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  style?: React.CSSProperties
  interactive?: boolean
}

export function Card({ children, className = '', style, interactive = false }: CardProps) {
  return (
    <div
      className={`rounded-md border transition-all duration-200 ${interactive ? 'hover:-translate-y-px hover:border-zinc-600 cursor-pointer' : ''} ${className}`}
      style={{
        background: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border)',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps {
  children: React.ReactNode
  className?: string
}

export function CardHeader({ children, className = '' }: CardHeaderProps) {
  return (
    <div
      className={`px-4 py-3 border-b flex items-center justify-between ${className}`}
      style={{ borderColor: 'var(--color-border)' }}
    >
      {children}
    </div>
  )
}

export function CardTitle({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <h3
      className={`text-sm font-semibold ${className}`}
      style={{ color: 'var(--color-text-secondary)' }}
    >
      {children}
    </h3>
  )
}

export function CardBody({
  children,
  className = '',
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={`p-4 ${className}`}>{children}</div>
}
