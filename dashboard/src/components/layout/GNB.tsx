import React from 'react'
import { NavLink } from 'react-router-dom'

const navLinks = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/receipts', label: 'Receipts' },
  { to: '/disputes', label: 'Disputes' },
  { to: '/settings', label: 'Settings' },
]

export function GNB() {
  return (
    <header
      className="sticky top-0 z-40 flex items-center px-4 h-14 border-b shrink-0"
      style={{
        background: 'var(--color-bg-elevated)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 mr-6">
        <div
          className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold"
          style={{ background: 'var(--color-accent)', color: '#fff' }}
        >
          SL
        </div>
        <span
          className="text-sm font-semibold tracking-tight hidden sm:block"
          style={{ color: 'var(--color-text-primary)' }}
        >
          SLAgent<span style={{ color: 'var(--color-accent)' }}>-402</span>
        </span>
      </div>

      {/* Nav */}
      <nav className="flex items-center gap-1 flex-1">
        {navLinks.map(({ to, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-xs font-medium transition-colors relative ${
                isActive
                  ? 'text-[--color-accent]'
                  : 'text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-zinc-800'
              }`
            }
            style={({ isActive }) =>
              isActive
                ? { color: 'var(--color-accent)' }
                : { color: 'var(--color-text-secondary)' }
            }
          >
            {({ isActive }) => (
              <>
                {label}
                {isActive && (
                  <span
                    className="absolute bottom-0 left-3 right-3 h-px"
                    style={{ background: 'var(--color-accent)' }}
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Right section */}
      <div className="flex items-center gap-3">
        {/* Network indicator */}
        <div className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full inline-block"
            style={{ background: 'var(--color-success)' }}
          />
          <span
            className="text-xs font-mono hidden sm:block"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Sepolia
          </span>
        </div>
        {/* Wallet button */}
        <button
          className="px-2.5 py-1 rounded text-xs font-medium border transition-colors"
          style={{
            background: 'transparent',
            borderColor: 'var(--color-border-strong)',
            color: 'var(--color-text-secondary)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-accent)'
            e.currentTarget.style.color = 'var(--color-accent)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-border-strong)'
            e.currentTarget.style.color = 'var(--color-text-secondary)'
          }}
        >
          Connect Wallet
        </button>
      </div>
    </header>
  )
}
