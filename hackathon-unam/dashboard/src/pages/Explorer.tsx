import { useState } from 'react'
import { useApi } from '../api'
import type { GameItem, PlayList } from '../types'
import { Card, Loading, Notice } from '../ui'

const PAGE = 25

export default function Explorer({ onPick }: { onPick: (game: string, play: string) => void }) {
  const games = useApi<{ items: GameItem[] }>('games')
  const [game, setGame] = useState('')
  const [q, setQ] = useState('')
  const [res, setRes] = useState('PASS')
  const [offset, setOffset] = useState(0)
  const qs = new URLSearchParams({ limit: String(PAGE), offset: String(offset) })
  if (game) qs.set('game_id', game)
  if (q.trim()) qs.set('q', q.trim())
  if (res) qs.set('pass_result', res)
  const plays = useApi<PlayList>(`plays?${qs.toString()}`)

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-black text-white">Explorador de jugadas</h2>
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-400">Partido
            <select value={game} onChange={(e) => { setGame(e.target.value); setOffset(0) }}
              className="mt-1 block rounded-md border border-white/10 bg-[#0b1220] px-3 py-2 text-sm text-white">
              <option value="">Todos</option>
              {games.data?.items.map((g) => (
                <option key={g.game_id} value={g.game_id}>
                  {g.home_team && g.visitor_team ? `${g.visitor_team} @ ${g.home_team} · ` : ''}{g.game_id}{g.n_plays ? ` (${g.n_plays} jugadas)` : ''}
                </option>
              ))}
            </select>
          </label>
          {plays.data?.filtro_resultado_disponible && (
            <label className="text-xs text-slate-400">Resultado
              <select value={res} onChange={(e) => { setRes(e.target.value); setOffset(0) }}
                className="mt-1 block rounded-md border border-white/10 bg-[#0b1220] px-3 py-2 text-sm text-white">
                <option value="PASS">Pases (C, I, IN)</option>
                <option value="C">Completos</option>
                <option value="I">Incompletos</option>
                <option value="IN">Intercepciones</option>
                <option value="S">Sacks</option>
                <option value="R">Scrambles</option>
                <option value="">Todas</option>
              </select>
            </label>
          )}
          {plays.data?.descripciones_disponibles && (
            <label className="text-xs text-slate-400">Buscar en la descripción
              <input value={q} onChange={(e) => { setQ(e.target.value); setOffset(0) }} placeholder="p. ej. incomplete"
                className="mt-1 block rounded-md border border-white/10 bg-[#0b1220] px-3 py-2 text-sm text-white" />
            </label>
          )}
          {plays.data && <span className="text-sm text-slate-400">{plays.data.total} jugadas</span>}
        </div>
      </Card>

      {plays.loading && <Loading what="jugadas" />}
      {plays.error && <Notice kind="error">{plays.error}</Notice>}
      {plays.data && plays.data.total === 0 && (
        <Notice kind="warn">No hay jugadas para mostrar. Coloca los CSV del evento en la carpeta data/ y reinicia el servidor.</Notice>
      )}
      <div className="grid gap-2">
        {plays.data?.items.map((p) => (
          <button key={`${p.game_id}-${p.play_id}`} disabled={!p.has_tracking} onClick={() => onPick(p.game_id, p.play_id)}
            className="rounded-lg border border-white/10 bg-[#0e1526] p-3 text-left hover:border-[#2EE6D6]/60 disabled:opacity-40">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span className="font-mono text-slate-200">Partido {p.game_id} · Jugada {p.play_id}</span>
              {p.quarter != null && <span>Q{p.quarter}</span>}
              {p.down != null && <span>{p.down}ª y {p.yards_to_go ?? '?'}</span>}
              {p.possession && <span>Ofensiva: {p.possession}</span>}
              {p.pass_result && <span>Resultado: {p.pass_result}</span>}
              {!p.has_tracking && <span className="text-amber-300">sin tracking</span>}
            </div>
            {p.description && <div className="mt-1 text-sm text-slate-200">{p.description}</div>}
          </button>
        ))}
      </div>
      {plays.data && plays.data.total > PAGE && (
        <div className="flex items-center gap-3">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} className="rounded bg-white/10 px-3 py-1 text-sm text-white disabled:opacity-30">← Anterior</button>
          <span className="text-xs text-slate-400">{offset + 1}–{Math.min(offset + PAGE, plays.data.total)}</span>
          <button disabled={offset + PAGE >= plays.data.total} onClick={() => setOffset(offset + PAGE)} className="rounded bg-white/10 px-3 py-1 text-sm text-white disabled:opacity-30">Siguiente →</button>
        </div>
      )}
    </div>
  )
}
