import React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { GNB } from './GNB'
import { ToastContainer } from '../ui/Toast'

export function Layout() {
  const { pathname } = useLocation()
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
    </div>
  )
}
