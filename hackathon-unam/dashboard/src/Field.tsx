import { useMemo } from 'react'
import type { Tracking } from './types'
import { COLORS } from './ui'

const W = 53.3
const L = 120

interface Props {
  tracking: Tracking
  frameIdx: number
  selected: string | null
  zone?: { x: number; y: number } | null
  onSelect: (id: string) => void
  proximity?: number
}

/** Campo NFL en SVG. Coordenadas en yardas; y se invierte para que crezca hacia arriba. */
export default function Field({ tracking, frameIdx, selected, zone, onSelect, proximity = 5 }: Props) {
  const fy = (y: number) => W - y

  const bounds = useMemo(() => {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity
    for (const p of tracking.players) {
      p.x.forEach((x, i) => {
        const y = p.y[i]
        if (x === null || y === null) return
        x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y)
      })
    }
    if (!Number.isFinite(x0)) return { x0: 0, x1: L, y0: 0, y1: W }
    const pad = 6
    // proporción mínima para que el campo no se vea deformado
    let w = Math.max(x1 - x0 + 2 * pad, 30)
    let h = Math.max(y1 - y0 + 2 * pad, 22)
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2
    const ratio = 1.9
    if (w / h < ratio) w = h * ratio; else h = w / ratio
    return { x0: cx - w / 2, x1: cx + w / 2, y0: cy - h / 2, y1: cy + h / 2 }
  }, [tracking])

  const vb = `${bounds.x0} ${W - bounds.y1} ${bounds.x1 - bounds.x0} ${bounds.y1 - bounds.y0}`
  const frame = tracking.frames[frameIdx]
  const at = (p: Tracking['players'][number], i: number) => {
    const x = p.x[i], y = p.y[i]
    return x === null || y === null ? null : { x, y }
  }

  const sel = tracking.players.find((p) => p.id === selected)
  const selPos = sel ? at(sel, frameIdx) : null
  const links = selPos
    ? tracking.players
        .filter((p) => p.class === 'defensor' || p.class === 'defensor_presion')
        .map((p) => ({ p, pos: at(p, frameIdx) }))
        .filter((o) => o.pos)
        .map((o) => ({ ...o, d: Math.hypot(o.pos!.x - selPos.x, o.pos!.y - selPos.y) }))
        .filter((o) => o.d <= proximity)
    : []

  const yardLines = []
  for (let x = 10; x <= 110; x += 5) yardLines.push(x)

  return (
    <svg viewBox={vb} className="w-full rounded-lg" role="img" aria-label="Campo de fútbol americano con posiciones de los jugadores">
      <rect x={0} y={0} width={L} height={W} fill="#10331f" />
      <rect x={0} y={0} width={10} height={W} fill="#0b2517" />
      <rect x={110} y={0} width={10} height={W} fill="#0b2517" />
      {Array.from({ length: 12 }).map((_, i) => (
        <rect key={i} x={10 + i * 10} y={0} width={5} height={W} fill="#ffffff" opacity={0.025} />
      ))}
      {yardLines.map((x) => (
        <line key={x} x1={x} x2={x} y1={0} y2={W} stroke="#fff" strokeOpacity={x % 10 === 0 ? 0.55 : 0.25} strokeWidth={x % 10 === 0 ? 0.25 : 0.15} />
      ))}
      {Array.from({ length: 99 }).map((_, i) => {
        const x = 10 + (i + 1) * (100 / 100)
        return (
          <g key={i} stroke="#fff" strokeOpacity={0.3} strokeWidth={0.1}>
            <line x1={x} x2={x} y1={0.6} y2={1.4} /><line x1={x} x2={x} y1={W - 1.4} y2={W - 0.6} />
            <line x1={x} x2={x} y1={W / 2 - 3.1 - 0.4} y2={W / 2 - 3.1 + 0.4} /><line x1={x} x2={x} y1={W / 2 + 3.1 - 0.4} y2={W / 2 + 3.1 + 0.4} />
          </g>
        )
      })}
      {[20, 30, 40, 50, 60, 70, 80, 90, 100].map((x) => {
        const n = x <= 60 ? x - 10 : 110 - x
        return (
          <g key={x} fill="#fff" fillOpacity={0.35} fontSize={2.6} fontWeight={700} textAnchor="middle">
            <text x={x} y={W - 5} >{n}</text>
            <text x={x} y={5} transform={`rotate(180 ${x} 4)`}>{n}</text>
          </g>
        )
      })}
      <rect x={0} y={0} width={L} height={W} fill="none" stroke="#fff" strokeOpacity={0.6} strokeWidth={0.3} />

      {zone && (
        <g>
          <circle cx={zone.x} cy={fy(zone.y)} r={proximity} fill="#FFC933" fillOpacity={0.06} stroke="#FFC933" strokeOpacity={0.5} strokeDasharray="0.8 0.6" strokeWidth={0.15} />
          <text x={zone.x} y={fy(zone.y) - proximity - 0.6} fontSize={1.3} fill="#FFC933" textAnchor="middle">zona de referencia</text>
        </g>
      )}
      {tracking.events.ball_land && (
        <g>
          <circle cx={tracking.events.ball_land.x} cy={fy(tracking.events.ball_land.y)} r={0.8} fill="none" stroke="#fff" strokeWidth={0.2} />
          <line x1={tracking.events.ball_land.x - 1} x2={tracking.events.ball_land.x + 1} y1={fy(tracking.events.ball_land.y)} y2={fy(tracking.events.ball_land.y)} stroke="#fff" strokeWidth={0.15} />
          <line y1={fy(tracking.events.ball_land.y) - 1} y2={fy(tracking.events.ball_land.y) + 1} x1={tracking.events.ball_land.x} x2={tracking.events.ball_land.x} stroke="#fff" strokeWidth={0.15} />
        </g>
      )}

      {/* rutas y trayectorias hasta el instante actual */}
      {tracking.players.map((p) => {
        const pts: string[] = []
        for (let i = 0; i <= frameIdx; i++) {
          const q = at(p, i)
          if (q) pts.push(`${q.x},${fy(q.y)}`)
        }
        if (pts.length < 2) return null
        const strong = p.class === 'objetivo' || p.class === 'receptor_no_objetivo' || p.id === selected
        return (
          <polyline key={`t${p.id}`} points={pts.join(' ')} fill="none" stroke={COLORS[p.class]}
            strokeOpacity={p.id === selected ? 0.95 : strong ? 0.6 : 0.22} strokeWidth={p.id === selected ? 0.38 : 0.2}
            strokeDasharray={p.side === 'defensiva' ? '0.5 0.4' : undefined} strokeLinejoin="round" />
        )
      })}

      {links.map((o) => (
        <g key={`l${o.p.id}`}>
          <line x1={selPos!.x} y1={fy(selPos!.y)} x2={o.pos!.x} y2={fy(o.pos!.y)} stroke="#fff" strokeOpacity={0.7} strokeWidth={0.15} strokeDasharray="0.4 0.3" />
          <text x={(selPos!.x + o.pos!.x) / 2} y={fy((selPos!.y + o.pos!.y) / 2) - 0.4} fontSize={1.2} fill="#fff" textAnchor="middle">{o.d.toFixed(1)} yd</text>
        </g>
      ))}

      {tracking.players.map((p) => {
        const q = at(p, frameIdx)
        if (!q) return null
        const isSel = p.id === selected
        const clickable = p.class === 'receptor_no_objetivo' || p.class === 'objetivo'
        return (
          <g key={p.id} transform={`translate(${q.x} ${fy(q.y)})`} onClick={() => clickable && onSelect(p.id)} style={{ cursor: clickable ? 'pointer' : 'default' }}>
            <title>{`${p.name ?? p.id} (${p.position ?? '?'}) · x=${q.x.toFixed(1)} y=${q.y.toFixed(1)}`}</title>
            {isSel && <circle r={1.7} fill="none" stroke="#fff" strokeWidth={0.2} />}
            {p.side === 'defensiva'
              ? <rect x={-0.8} y={-0.8} width={1.6} height={1.6} fill={COLORS[p.class]} stroke="#000" strokeOpacity={0.5} strokeWidth={0.12} />
              : <circle r={0.95} fill={COLORS[p.class]} stroke="#000" strokeOpacity={0.5} strokeWidth={0.12} />}
            <text y={-1.3} fontSize={1.25} fill="#fff" textAnchor="middle" fontWeight={700} style={{ paintOrder: 'stroke' }} stroke="#000" strokeWidth={0.18}>
              {p.position ?? p.id}
            </text>
          </g>
        )
      })}
      <text x={bounds.x0 + 1} y={W - bounds.y1 + 2.2} fontSize={1.5} fill="#fff" opacity={0.8}>cuadro {frame}</text>
    </svg>
  )
}
