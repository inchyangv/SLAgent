import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Menu, X } from 'lucide-react'

const navLinks = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/receipts', label: 'Receipts' },
  { to: '/disputes', label: 'Disputes' },
  { to: '/settings', label: 'Settings' },
]

export function GNB() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      <header
        className="sticky top-0 z-40 flex items-center px-4 h-14 border-b shrink-0"
        style={{
          background: 'var(--color-bg-elevated)',
          borderColor: 'var(--color-border-subtle)',
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 mr-6 shrink-0">
          <div
            className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold"
            style={{ background: 'var(--color-accent)', color: '#fff' }}
          >
            SL
          </div>
          <span
            className="text-sm font-semibold tracking-tight"
            style={{ color: 'var(--color-text-primary)' }}
          >
            SLAgent<span style={{ color: 'var(--color-accent)' }}>-402</span>
          </span>
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1 flex-1">
          {navLinks.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className="relative px-3 py-1.5 rounded text-xs font-medium transition-colors"
              style={({ isActive }) => ({
                color: isActive ? 'var(--color-accent)' : 'var(--color-text-secondary)',
              })}
            >
              {({ isActive }) => (
                <>
                  <span
                    className="transition-colors hover:text-white"
                    onMouseEnter={(e) => {
                      if (!isActive) e.currentTarget.style.color = 'var(--color-text-primary)'
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) e.currentTarget.style.color = ''
                    }}
                  >
                    {label}
                  </span>
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
        <div className="flex items-center gap-3 ml-auto">
          {/* Network indicator */}
          <div className="hidden sm:flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full inline-block animate-pulse"
              style={{ background: 'var(--color-success)' }}
            />
            <span
              className="text-xs font-mono"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Sepolia
            </span>
          </div>

          {/* Wallet button */}
          <button
            className="px-3 py-1 rounded text-xs font-medium border transition-all duration-150"
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

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-1.5 rounded transition-colors"
            style={{ color: 'var(--color-text-secondary)' }}
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </header>

      {/* Mobile menu */}
      {mobileOpen && (
        <div
          className="md:hidden sticky top-14 z-30 border-b px-4 py-3 flex flex-col gap-1"
          style={{
            background: 'var(--color-bg-elevated)',
            borderColor: 'var(--color-border)',
          }}
        >
          {navLinks.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMobileOpen(false)}
              className="px-3 py-2 rounded text-sm font-medium transition-colors"
              style={({ isActive }) => ({
                color: isActive ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                background: isActive ? 'rgba(74, 158, 255, 0.08)' : 'transparent',
              })}
            >
              {label}
            </NavLink>
          ))}

          {/* Network in mobile */}
          <div className="flex items-center gap-1.5 px-3 py-2 mt-1">
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: 'var(--color-success)' }}
            />
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Sepolia
            </span>
          </div>
        </div>
      )}
    </>
  )
}
