import { useState } from 'react'
import { api } from '../api'
import type { Dvi, NovaResult } from '../types'
import { Card, Notice, playerLabel } from '../ui'

interface Props { game: string; play: string; dvi: Dvi | null; selected: string | null }

export default function NovaPage({ game, play, dvi, selected }: Props) {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<NovaResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const receivers = dvi?.receivers.filter((r) => r.dvi != null) ?? []
  const [rid, setRid] = useState<string>(selected ?? '')

  async function run() {
    setBusy(true); setErr(null); setRes(null)
    try {
      const body = { receiver_id: rid || null, question: question.trim() || null }
      setRes(await api<NovaResult>(`plays/${game}/${play}/nova`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }))
    } catch (e) {
      setErr((e as Error).message)
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-black text-white">Análisis con Amazon Nova</h2>
      <Notice kind="info">Nova solo explica las métricas calculadas por el motor de DECOY IQ; no calcula ni inventa métricas. El resto de la plataforma funciona sin esta sección.</Notice>
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-400">Receptor
            <select value={rid} onChange={(e) => setRid(e.target.value)} className="mt-1 block rounded-md border border-white/10 bg-[#0b1220] px-3 py-2 text-sm text-white">
              <option value="">Todos los receptores</option>
              {receivers.map((r) => <option key={r.id} value={r.id}>{playerLabel(r)}</option>)}
            </select>
          </label>
          <label className="min-w-[240px] flex-1 text-xs text-slate-400">Enfoque opcional
            <input value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} placeholder="p. ej. ¿Qué defensor se movió más?"
              className="mt-1 block w-full rounded-md border border-white/10 bg-[#0b1220] px-3 py-2 text-sm text-white" />
          </label>
          <button onClick={run} disabled={busy || !dvi?.available} className="rounded-lg bg-[#FFC933] px-4 py-2 text-sm font-bold text-black disabled:opacity-40">
            {busy ? 'Consultando…' : 'Generar explicación'}
          </button>
        </div>
      </Card>
      {err && <Notice kind="error">{err}</Notice>}
      {res && !res.available && <Notice kind="warn">{res.error ?? 'Explicación no disponible.'} La plataforma sigue funcionando con los cálculos matemáticos.</Notice>}
      {res?.available && (
        <Card title={`Explicación · ${res.model_id}`}>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{res.text}</div>
          <p className="mt-3 text-xs text-slate-500">Texto generado por un modelo de lenguaje a partir de las métricas del motor. Puede contener imprecisiones; contrástalo con los indicadores.</p>
        </Card>
      )}
    </div>
  )
}
