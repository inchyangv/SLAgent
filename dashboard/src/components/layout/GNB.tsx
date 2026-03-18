import { useState, useRef, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { Menu, X, Bell } from 'lucide-react'
import { ConnectButton } from '@rainbow-me/rainbowkit'
import { useNetwork } from '../../hooks/useNetwork'
import { useLogStore } from '../../store/log'
import type { LogEntry } from '../../store/log'

const navLinks = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/receipts', label: 'Receipts' },
  { to: '/disputes', label: 'Disputes' },
  { to: '/settings', label: 'Settings' },
]

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  return `${Math.floor(diff / 3_600_000)}h ago`
}

function notifIcon(type: LogEntry['type']): { icon: string; color: string } {
  if (type === 'err') return { icon: '✗', color: 'var(--color-error)' }
  if (type === 'ok') return { icon: '✓', color: 'var(--color-success)' }
  return { icon: '·', color: 'var(--color-text-muted)' }
}

function NotificationDropdown({ onClose }: { onClose: () => void }) {
  const entries = useLogStore((s) => s.entries)
  const markAllRead = useLogStore((s) => s.markAllRead)

  const recent = entries.slice(0, 20)

  return (
    <div
      className="absolute right-0 top-full mt-1 w-80 rounded-lg border shadow-2xl z-50 overflow-hidden"
      style={{ background: 'var(--color-bg-elevated)', borderColor: 'var(--color-border-strong)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <span className="text-xs font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
          Notifications
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { markAllRead(); onClose() }}
            className="text-xs transition-colors"
            style={{ color: 'var(--color-accent)' }}
          >
            Mark all read
          </button>
          <button
            onClick={onClose}
            className="p-0.5 rounded hover:bg-zinc-800 transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <X size={12} />
          </button>
        </div>
      </div>

      {/* List */}
      <div className="overflow-y-auto" style={{ maxHeight: 320 }}>
        {recent.length === 0 ? (
          <div className="flex flex-col items-center py-8 gap-2">
            <Bell size={20} style={{ color: 'var(--color-text-muted)' }} />
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              No notifications yet
            </p>
          </div>
        ) : (
          recent.map((entry) => {
            const { icon, color } = notifIcon(entry.type)
            return (
              <div
                key={entry.id}
                className="flex items-start gap-3 px-3 py-2 border-b last:border-0 hover:bg-zinc-800 transition-colors"
                style={{ borderColor: 'var(--color-border-subtle)' }}
              >
                <span className="text-sm shrink-0 mt-0.5" style={{ color }}>
                  {icon}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
                    {entry.msg}
                  </p>
                </div>
                <span
                  className="text-xs font-mono shrink-0"
                  style={{ color: 'var(--color-text-muted)', fontSize: '10px' }}
                >
                  {relativeTime(entry.ts)}
                </span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export function GNB() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const { isConnected, networkName, isCorrectNetwork } = useNetwork()
  const unreadCount = useLogStore((s) => s.unreadCount)
  const markAllRead = useLogStore((s) => s.markAllRead)
  const notifRef = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    if (!notifOpen) return
    function handler(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [notifOpen])

  function handleBellClick() {
    if (!notifOpen) markAllRead()
    setNotifOpen((v) => !v)
  }

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
                  ? isCorrectNetwork ? 'var(--color-success)' : 'var(--color-warning)'
                  : 'var(--color-text-muted)',
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

          {/* Notification bell */}
          <div ref={notifRef} className="relative">
            <button
              onClick={handleBellClick}
              className="relative p-1.5 rounded transition-colors hover:bg-zinc-800"
              style={{ color: unreadCount > 0 ? 'var(--color-accent)' : 'var(--color-text-muted)' }}
              aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
            >
              <Bell size={16} />
              {unreadCount > 0 && (
                <span
                  className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 px-0.5 rounded-full text-xs font-bold flex items-center justify-center"
                  style={{ background: 'var(--color-error)', color: '#fff', fontSize: '9px' }}
                >
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>
            {notifOpen && <NotificationDropdown onClose={() => setNotifOpen(false)} />}
          </div>

          {/* RainbowKit wallet button */}
          <ConnectButton accountStatus="avatar" chainStatus="icon" showBalance={false} />

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
