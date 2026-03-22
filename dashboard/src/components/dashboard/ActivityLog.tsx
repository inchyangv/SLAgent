import React, { useRef, useEffect } from 'react'
import { Trash2 } from 'lucide-react'
import { useLogStore } from '../../store/log'
import { Card, CardHeader, CardTitle, CardBody } from '../ui/Card'

const typeStyle: Record<string, string> = {
  ok: 'var(--color-success)',
  err: 'var(--color-error)',
  info: 'var(--color-text-muted)',
}

const typePrefix: Record<string, string> = {
  ok: '✓',
  err: '✗',
  info: '·',
}

export function ActivityLog() {
  const entries = useLogStore((s) => s.entries)
  const clear = useLogStore((s) => s.clear)
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll within container only (not the whole page)
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [entries.length])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Activity Log ({entries.length})</CardTitle>
        <button
          onClick={clear}
          className="p-1 rounded hover:bg-zinc-800 transition-colors"
          style={{ color: 'var(--color-text-muted)' }}
          title="Clear log"
        >
          <Trash2 size={13} />
        </button>
      </CardHeader>
      <CardBody className="p-0">
        <div
          ref={containerRef}
          className="overflow-y-auto font-mono text-xs px-3 py-2"
          style={{
            maxHeight: 160,
            background: 'var(--color-bg-primary)',
          }}
        >
          {entries.length === 0 ? (
            <span style={{ color: 'var(--color-text-muted)' }}>No activity yet.</span>
          ) : (
            [...entries].reverse().map((e) => (
              <div key={e.id} className="flex items-start gap-1.5 py-0.5 leading-5">
                <span
                  className="shrink-0"
                  style={{ color: typeStyle[e.type] ?? typeStyle.info }}
                >
                  {typePrefix[e.type] ?? '·'}
                </span>
                <span className="shrink-0" style={{ color: 'var(--color-text-muted)' }}>
                  {new Date(e.ts).toLocaleTimeString('en-US', { hour12: false })}
                </span>
                <span style={{ color: 'var(--color-text-secondary)', wordBreak: 'break-all' }}>
                  {e.msg}
                </span>
              </div>
            ))
          )}
        </div>
      </CardBody>
    </Card>
  )
}
