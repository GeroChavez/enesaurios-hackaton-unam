import { ReactNode } from 'react'
import type { PlayerClass } from './types'

export const COLORS: Record<PlayerClass, string> = {
  objetivo: '#FFC933',
  receptor_no_objetivo: '#2EE6D6',
  pasador: '#F4F6FB',
  ofensiva_otro: '#7C8AA5',
  defensor: '#FF4D5E',
  defensor_presion: '#B8323F',
  balon: '#C98A4B',
  desconocido: '#556079',
}
export const CLASS_LABEL: Record<PlayerClass, string> = {
  objetivo: 'Receptor objetivo',
  receptor_no_objetivo: 'Receptor no objetivo',
  pasador: 'Pasador',
  ofensiva_otro: 'Otro ofensivo',
  defensor: 'Defensor',
  defensor_presion: 'Defensor (presión)',
  balon: 'Balón',
  desconocido: 'Sin clasificar',
}

export function Card({ title, children, className = '', right }: { title?: string; children: ReactNode; className?: string; right?: ReactNode }) {
  return (
    <section className={`rounded-xl border border-white/10 bg-[#0e1526] p-4 shadow-lg ${className}`}>
      {(title || right) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</h3>
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0e1526] p-4">
      <div className="text-xs uppercase tracking-widest text-slate-400">{label}</div>
      <div className="mt-1 text-3xl font-black text-white tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  )
}

export function Notice({ kind = 'info', children }: { kind?: 'info' | 'warn' | 'error'; children: ReactNode }) {
  const c = kind === 'error' ? 'border-red-500/40 bg-red-500/10 text-red-200'
    : kind === 'warn' ? 'border-amber-400/40 bg-amber-400/10 text-amber-100'
    : 'border-sky-400/30 bg-sky-400/10 text-sky-100'
  return <div className={`rounded-lg border px-3 py-2 text-sm ${c}`}>{children}</div>
}

export function Loading({ what = 'datos' }: { what?: string }) {
  return <div className="animate-pulse text-sm text-slate-400">Cargando {what}…</div>
}

export const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined || !Number.isFinite(v) ? '—' : v.toFixed(d))

export function playerLabel(p: { name: string | null; position: string | null; id: string }) {
  return `${p.name ?? 'Jugador ' + p.id}${p.position ? ' · ' + p.position : ''}`
}
