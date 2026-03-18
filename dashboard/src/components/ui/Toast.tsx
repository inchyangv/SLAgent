import React, { useEffect } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useToastStore } from '../../store/toast'
import type { ToastType } from '../../store/toast'

const toastIcons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={16} />,
  error: <XCircle size={16} />,
  warning: <AlertTriangle size={16} />,
  info: <Info size={16} />,
}

const toastStyles: Record<ToastType, string> = {
  success: 'border-green-800 text-green-300',
  error: 'border-red-800 text-red-300',
  warning: 'border-amber-800 text-amber-300',
  info: 'border-blue-800 text-blue-300',
}

const AUTO_DISMISS_MS = 5000

function ToastItem({ id, message, type }: { id: string; message: string; type: ToastType }) {
  const removeToast = useToastStore((s) => s.removeToast)

  useEffect(() => {
    const timer = setTimeout(() => removeToast(id), AUTO_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [id, removeToast])

  return (
    <div
      className={`flex items-start gap-2 px-3 py-2 rounded-md border text-sm shadow-lg slide-in-right ${toastStyles[type]}`}
      style={{ background: 'var(--color-bg-elevated)', minWidth: 260, maxWidth: 380 }}
    >
      <span className="mt-0.5 shrink-0">{toastIcons[type]}</span>
      <span className="flex-1 text-xs" style={{ color: 'var(--color-text-primary)' }}>
        {message}
      </span>
      <button
        onClick={() => removeToast(id)}
        className="shrink-0 p-0.5 rounded hover:bg-zinc-700 transition-colors"
        style={{ color: 'var(--color-text-muted)' }}
      >
        <X size={12} />
      </button>
    </div>
  )
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => (
        <ToastItem key={t.id} {...t} />
      ))}
    </div>
  )
}
