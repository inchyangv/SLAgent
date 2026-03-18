import React from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, className = '', ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label
          className="text-xs font-medium"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {label}
        </label>
      )}
      <input
        className={`px-2.5 py-1.5 rounded text-sm border outline-none transition-colors ${className}`}
        style={{
          background: 'var(--color-bg-elevated)',
          borderColor: error ? 'var(--color-error)' : 'var(--color-border)',
          color: 'var(--color-text-primary)',
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = 'var(--color-accent)'
          props.onFocus?.(e)
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = error
            ? 'var(--color-error)'
            : 'var(--color-border)'
          props.onBlur?.(e)
        }}
        {...props}
      />
      {error && (
        <span className="text-xs" style={{ color: 'var(--color-error)' }}>
          {error}
        </span>
      )}
    </div>
  )
}
