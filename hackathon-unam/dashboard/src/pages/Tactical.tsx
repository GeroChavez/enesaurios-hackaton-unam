import { useEffect, useMemo, useState } from 'react'
import Field from '../Field'
import type { Dvi, PlayDetail, Tracking } from '../types'
import { CLASS_LABEL, COLORS, Card, Notice, fmt, playerLabel } from '../ui'
import type { PlayerClass } from '../types'

interface Props {
  detail: PlayDetail
  tracking: Tracking
  dvi: Dvi | null
  selected: string | null
  setSelected: (id: string) => void
}

export default function Tactical({ detail, tracking, dvi, selected, setSelected }: Props) {
  const n = tracking.frames.length
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => { setIdx(0); setPlaying(false) }, [tracking])
  useEffect(() => {
    if (!playing) return
    const h = window.setInterval(() => setIdx((i) => { if (i >= n - 1) { setPlaying(false); return i } return i + 1 }), Math.max(60, detail.time.dt_s * 1000))
    return () => window.clearInterval(h)
  }, [playing, n, detail.time.dt_s])

  const ev = tracking.events
  const frame = tracking.frames[idx]
  const idxOf = (f: number | null) => (f === null ? -1 : tracking.frames.indexOf(f))
  const phase = ev.throw_frame !== null ? (frame < ev.throw_frame ? 'antes del lanzamiento' : frame === ev.throw_frame ? 'lanzamiento' : 'después del lanzamiento') : 'lanzamiento no identificado'
  const legend = useMemo(() => Array.from(new Set(tracking.players.map((p) => p.class))) as PlayerClass[], [tracking])
  const recvs = tracking.players.filter((p) => p.class === 'objetivo' || p.class === 'receptor_no_objetivo')

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-black text-white">Visualización táctica</h2>
      {dvi?.target_inferred && <Notice kind="info">El receptor objetivo (dorado) es una <strong>inferencia</strong>: se dedujo comparando el nombre de la descripción de la jugada con los corredores de ruta. No es un dato oficial.</Notice>}
      {!tracking.orientation_normalized && <Notice kind="warn">No se conoce la dirección de la jugada: las coordenadas se muestran tal como vienen en los datos (sin normalizar).</Notice>}
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <Card>
          <Field tracking={tracking} frameIdx={idx} selected={selected} zone={dvi?.zone} onSelect={setSelected} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button onClick={() => setIdx(0)} className="rounded bg-white/10 px-2 py-1 text-sm text-white" title="Inicio">⏮</button>
            <button onClick={() => setIdx(Math.max(0, idx - 1))} className="rounded bg-white/10 px-2 py-1 text-sm text-white" title="Cuadro anterior">◀</button>
            <button onClick={() => { if (idx >= n - 1) setIdx(0); setPlaying(!playing) }} className="rounded bg-[#2EE6D6] px-3 py-1 text-sm font-bold text-black">{playing ? 'Pausa' : 'Reproducir'}</button>
            <button onClick={() => setIdx(Math.min(n - 1, idx + 1))} className="rounded bg-white/10 px-2 py-1 text-sm text-white" title="Cuadro siguiente">▶</button>
            <button onClick={() => setIdx(n - 1)} className="rounded bg-white/10 px-2 py-1 text-sm text-white" title="Final">⏭</button>
            {idxOf(ev.throw_frame) >= 0 && <button onClick={() => setIdx(idxOf(ev.throw_frame))} className="rounded border border-[#FFC933]/50 px-2 py-1 text-xs text-[#FFC933]">Ir al lanzamiento</button>}
            {idxOf(ev.arrival_frame) >= 0 && <button onClick={() => setIdx(idxOf(ev.arrival_frame))} className="rounded border border-white/30 px-2 py-1 text-xs text-white">Ir a la llegada</button>}
            <span className="ml-auto text-xs text-slate-400">cuadro {frame} · t = {fmt(tracking.t_s[idx], 1)} s · {phase}</span>
          </div>
          <input type="range" min={0} max={n - 1} value={idx} onChange={(e) => setIdx(Number(e.target.value))} className="mt-2 w-full accent-[#2EE6D6]" aria-label="Instante de la jugada" />
        </Card>

        <div className="space-y-4">
          <Card title="Leyenda">
            <ul className="space-y-1 text-sm">
              {legend.map((c) => (
                <li key={c} className="flex items-center gap-2 text-slate-200">
                  <span className="inline-block h-3 w-3" style={{ background: COLORS[c], borderRadius: c.startsWith('defensor') ? 2 : 999 }} />{CLASS_LABEL[c]}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-slate-500">Cuadrado = defensa, círculo = ofensiva. Línea punteada = trayectoria defensiva. Haz clic en un receptor para ver los defensores a ≤ 5 yd.</p>
          </Card>
          <Card title="Receptores">
            <ul className="space-y-1">
              {recvs.map((p) => {
                const r = dvi?.receivers.find((x) => x.id === p.id)
                return (
                  <li key={p.id}>
                    <button onClick={() => setSelected(p.id)} className={`flex w-full items-center justify-between rounded px-2 py-1 text-left text-sm ${selected === p.id ? 'bg-white/15' : 'hover:bg-white/5'}`}>
                      <span style={{ color: COLORS[p.class] }}>{playerLabel(p)}</span>
                      <span className="text-xs text-slate-400">{p.class === 'objetivo' ? 'objetivo' : r?.dvi != null ? `DVI ${fmt(r.dvi, 1)}` : ''}</span>
                    </button>
                  </li>
                )
              })}
              {recvs.length === 0 && <li className="text-sm text-slate-400">No se identificaron receptores con los datos disponibles.</li>}
            </ul>
          </Card>
          <Card title="Datos de la jugada">
            <dl className="space-y-1 text-xs text-slate-300">
              <div>Partido {detail.game_id} · Jugada {detail.play_id}</div>
              <div>Cuadros: {detail.data_quality.frames} · Jugadores: {detail.data_quality.jugadores}</div>
              <div>Celdas sin dato: {detail.data_quality.celdas_sin_dato} de {detail.data_quality.celdas_totales}</div>
              <div>Lanzamiento: {ev.throw_frame ?? 'no identificado'}{ev.throw_source ? ` (${ev.throw_source})` : ''}</div>
              <div>Intervalo entre cuadros: {fmt(detail.time.dt_s, 2)} s ({detail.time.source})</div>
              {detail.info.description ? <div className="pt-1 text-slate-200">{String(detail.info.description)}</div> : null}
            </dl>
            {detail.notes.map((t) => <div key={t} className="mt-2"><Notice kind="warn">{t}</Notice></div>)}
          </Card>
        </div>
      </div>
    </div>
  )
}
