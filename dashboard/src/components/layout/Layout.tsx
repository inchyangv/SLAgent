import React, { useState, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { GNB } from './GNB'
import { ToastContainer } from '../ui/Toast'
import { CommandPalette } from '../ui/CommandPalette'

export function Layout() {
  const { pathname } = useLocation()
  const [paletteOpen, setPaletteOpen] = useState(false)

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'var(--color-bg-primary)' }}
    >
      <GNB />
      <main className="flex-1 overflow-auto">
        <div key={pathname} className="page-fade-in">
          <Outlet />
        </div>
      </main>
      <ToastContainer />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
