import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { ConnectButton } from '@rainbow-me/rainbowkit'
import { useNetwork } from '../../hooks/useNetwork'

const navLinks = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/receipts', label: 'Receipts' },
  { to: '/disputes', label: 'Disputes' },
  { to: '/settings', label: 'Settings' },
]

export function GNB() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { isConnected, networkName, isCorrectNetwork } = useNetwork()

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
        <div className="flex items-center gap-3 ml-auto">
          {/* Network indicator */}
          <div className="hidden sm:flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full inline-block"
              style={{
                background: isConnected
                  ? (isCorrectNetwork ? 'var(--color-success)' : 'var(--color-warning)')
                  : 'var(--color-text-muted)',
                animation: isConnected ? 'pulse 2s infinite' : 'none',
              }}
            />
            <span
              className="text-xs font-mono"
              style={{
                color: !isCorrectNetwork && isConnected
                  ? 'var(--color-warning)'
                  : 'var(--color-text-secondary)',
              }}
            >
              {isConnected ? networkName : 'Sepolia'}
            </span>
          </div>

          {/* RainbowKit wallet button */}
          <ConnectButton
            accountStatus="avatar"
            chainStatus="icon"
            showBalance={false}
          />

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
              style={{
                background: isConnected && isCorrectNetwork
                  ? 'var(--color-success)'
                  : 'var(--color-text-muted)',
              }}
            />
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {isConnected ? networkName : 'Not connected'}
            </span>
          </div>
        </div>
      )}
    </>
  )
}
