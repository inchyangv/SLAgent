import React from 'react'
import { Outlet } from 'react-router-dom'
import { GNB } from './GNB'
import { ToastContainer } from '../ui/Toast'

export function Layout() {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'var(--color-bg-primary)' }}
    >
      <GNB />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      <ToastContainer />
    </div>
  )
}
