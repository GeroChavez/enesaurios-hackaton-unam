import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi } from '../api'
import type { Dvi, Methodology } from '../types'
import { Card, Loading, Notice, fmt, playerLabel } from '../ui'

const LINE_COLORS: Record<string, string> = { dvi: '#FFC933', pdp: '#2EE6D6', arrastre: '#FF4D5E', espacio_objetivo: '#9B8CFF', espacio_companeros: '#7BE495' }
const tip = { contentStyle: { background: '#0b1220', border: '1px solid rgba(255,255,255,.15)', color: '#fff' } }

interface Props { dvi: Dvi | null; loading: boolean; error: string | null; selected: string | null; setSelected: (id: string) => void }

export default function DviPage({ dvi, loading, error, selected, setSelected }: Props) {
  const meth = useApi<Methodology>('methodology')
  if (loading) return <Loading what="DVI" />
  if (error) return <Notice kind="error">{error}</Notice>
  if (!dvi) return <Notice kind="info">Selecciona una jugada en el explorador.</Notice>
  if (!dvi.available) return <Notice kind="warn">DVI no calculable para esta jugada: {dvi.reason}</Notice>

  const withDvi = dvi.receivers.filter((r) => r.dvi != null)
  const cur = withDvi.find((r) => r.id === selected) ?? withDvi[0]
  const compare = withDvi.map((r) => ({ id: r.id, label: r.name ?? r.id, dvi: Number(fmt(r.dvi, 1)) }))
  const contrib = (cur.components ?? []).map((c) => ({
    name: c.label, aporte: c.normalized == null ? 0 : Number((100 * c.weight * c.normalized).toFixed(2)), maximo: 100 * c.weight,
  }))

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-black text-white">Análisis DVI <span className="ml-2 rounded bg-amber-400/20 px-2 py-0.5 align-middle text-xs font-semibold text-amber-200">EXPERIMENTAL</span></h2>
      <Notice kind="warn">Pesos, saturaciones y σ son criterio del equipo: <strong>no están calibrados</strong> ni validados contra resultados reales.</Notice>
      {dvi.warnings.map((w) => <Notice key={w} kind="warn">{w}</Notice>)}
      {dvi.local_summary && (
        <Card title="Resumen automático (calculado, sin IA)">
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{dvi.local_summary}</div>
        </Card>
      )}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Comparación entre receptores no objetivo" className="lg:col-span-1">
          <div style={{ height: Math.max(180, compare.length * 44) }}>
            <ResponsiveContainer>
              <BarChart data={compare} layout="vertical" margin={{ left: 10, right: 16 }}>
                <CartesianGrid stroke="#ffffff14" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="#94a3b8" />
                <YAxis type="category" dataKey="label" width={90} stroke="#94a3b8" fontSize={11} />
                <Tooltip {...tip} />
                <Bar dataKey="dvi" name="DVI" onClick={(d: unknown) => { const o = d as { id?: string; payload?: { id?: string } }; const id = o.id ?? o.payload?.id; if (id) setSelected(id) }}>
                  {compare.map((c) => <Cell key={c.id} fill={c.id === cur.id ? '#FFC933' : '#2EE6D6'} cursor="pointer" />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title={`DVI de ${playerLabel(cur)}`} className="lg:col-span-2">
          <div className="flex flex-wrap items-center gap-6">
            <div>
              <div className="text-6xl font-black text-[#FFC933] tabular-nums">{fmt(cur.dvi, 1)}</div>
              <div className="text-xs text-slate-400">de 100 · cobertura de pesos {fmt((cur.weight_coverage ?? 0) * 100, 0)}%</div>
            </div>
            <div className="min-w-[260px] flex-1" style={{ height: 150 }}>
              <ResponsiveContainer>
                <BarChart data={contrib} layout="vertical" margin={{ left: 10, right: 16 }}>
                  <CartesianGrid stroke="#ffffff14" horizontal={false} />
                  <XAxis type="number" domain={[0, 30]} stroke="#94a3b8" unit=" pts" />
                  <YAxis type="category" dataKey="name" width={150} stroke="#94a3b8" fontSize={10} />
                  <Tooltip {...tip} />
                  <Bar dataKey="aporte" name="Aporte al DVI (puntos)" fill="#2EE6D6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Desglose de componentes">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-200">
            <thead className="text-xs uppercase text-slate-400"><tr><th className="py-1 pr-3">Componente</th><th className="pr-3">Valor</th><th className="pr-3">Unidad</th><th className="pr-3">Normalizado [0,1]</th><th className="pr-3">Peso</th><th>Nota</th></tr></thead>
            <tbody>
              {(cur.components ?? []).map((c) => (
                <tr key={c.key} className="border-t border-white/5">
                  <td className="py-1.5 pr-3">{c.label}</td><td className="pr-3 tabular-nums">{fmt(c.raw, 2)}</td><td className="pr-3 text-slate-400">{c.unit}</td>
                  <td className="pr-3 tabular-nums">{fmt(c.normalized, 2)}</td><td className="pr-3 tabular-nums">{fmt(c.weight, 2)}</td>
                  <td className="text-xs text-amber-200">{c.normalized == null ? 'No calculable. ' : ''}{c.note ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Evolución temporal (ventana acumulada hasta cada cuadro)">
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={cur.series ?? []} margin={{ left: 0, right: 16 }}>
                <CartesianGrid stroke="#ffffff14" />
                <XAxis dataKey="t_s" stroke="#94a3b8" tickFormatter={(v: number) => `${v.toFixed(1)}s`} />
                <YAxis stroke="#94a3b8" domain={[0, 100]} />
                <Tooltip {...tip} formatter={(v: unknown) => (typeof v === 'number' ? v.toFixed(2) : '—')} labelFormatter={(l: unknown) => `t = ${Number(l).toFixed(1)} s`} />
                <Line type="monotone" dataKey="dvi" name="DVI" stroke={LINE_COLORS.dvi} dot={false} strokeWidth={2.5} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Componentes normalizados en el tiempo">
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={cur.series ?? []} margin={{ left: 0, right: 16 }}>
                <CartesianGrid stroke="#ffffff14" />
                <XAxis dataKey="t_s" stroke="#94a3b8" tickFormatter={(v: number) => `${v.toFixed(1)}s`} />
                <YAxis stroke="#94a3b8" domain={[0, 1]} />
                <Tooltip {...tip} formatter={(v: unknown) => (typeof v === 'number' ? v.toFixed(2) : '—')} />
                <Legend />
                {(cur.components ?? []).map((c) => (
                  <Line key={c.key} type="monotone" dataKey={c.key} name={c.label} stroke={LINE_COLORS[c.key]} dot={false} connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Defensores con mayor proximidad potencial">
          {(cur.closest_defenders ?? []).length === 0 && <p className="text-sm text-slate-400">Ningún defensor estuvo cerca de este receptor en la ventana.</p>}
          <ul className="space-y-1 text-sm text-slate-200">
            {(cur.closest_defenders ?? []).map((d) => (
              <li key={d.id}>{playerLabel(d)} · peso {fmt(d.peso_proximidad)} · distancia media {fmt(d.distancia_media_yd, 1)} yd · mínima {fmt(d.distancia_minima_yd, 1)} yd</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">Proximidad geométrica, no atención visual: los datos no incluyen mirada ni asignaciones de cobertura.</p>
        </Card>
        <Card title="Ventana y supuestos">
          <ul className="space-y-1 text-xs text-slate-300">
            <li>Cuadros {dvi.window.start_frame} → {dvi.window.end_frame}; lanzamiento: {dvi.window.throw_frame ?? 'no identificado'}{dvi.window.throw_source ? ` (${dvi.window.throw_source})` : ''}.</li>
            <li>Intervalo: {fmt(dvi.window.dt_s, 2)} s ({dvi.window.dt_source}).</li>
            <li>Inicio de ventana: {dvi.window.start_source ?? '—'}.</li>
            <li>Zona de referencia: {dvi.zone_source}.</li>
          </ul>
        </Card>
      </div>

      <Card title="Metodología y limitaciones">
        {meth.loading && <Loading what="metodología" />}
        {meth.data && (
          <div className="space-y-3 text-sm text-slate-300">
            <Notice kind="warn">{meth.data.estado}</Notice>
            <p><strong>Escala:</strong> {meth.data.escala}</p>
            <p><strong>Ventana:</strong> {meth.data.ventana}</p>
            <p><strong>Núcleo de proximidad:</strong> <code>{meth.data.nucleo.formula}</code>, σ = {meth.data.nucleo.sigma_yd} yd.</p>
            {meth.data.componentes.map((c) => (
              <div key={c.key} className="rounded border border-white/10 p-3">
                <div className="font-semibold text-white">{c.label} <span className="text-xs text-slate-400">({c.unit}; peso {c.weight}; saturación {c.ref})</span></div>
                <div className="mt-1 font-mono text-xs text-[#2EE6D6]">{c.formula}</div>
                <div className="mt-1">{c.measures}</div>
                <div className="mt-1 text-xs text-amber-200">Limitación: {c.limitation}</div>
              </div>
            ))}
            <p><strong>Calibración:</strong> {meth.data.calibracion}</p>
            <p><strong>Observado vs. inferido:</strong> {meth.data.observado_vs_inferido}</p>
            <p><strong>Pesos:</strong> {meth.data.pesos}</p>
            <p><strong>Doble conteo:</strong> {meth.data.doble_conteo}</p>
            <p><strong>Componentes no calculables:</strong> {meth.data.no_calculable}</p>
          </div>
        )}
      </Card>
    </div>
  )
}
