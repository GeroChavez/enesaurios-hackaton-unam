import { useApi } from '../api'
import type { DataStatus } from '../types'
import { Card, Loading, Notice, Stat } from '../ui'

export default function Home({ go }: { go: (p: 'explorer') => void }) {
  const { data, error, loading } = useApi<DataStatus>('data/status')
  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-[#12325a] via-[#0e1526] to-[#0b1220] p-8">
        <div className="text-xs font-bold uppercase tracking-[0.3em] text-[#FFC933]">Hackathon NFL × Amazon · ENES Juriquilla UNAM</div>
        <h1 className="mt-2 text-5xl font-black tracking-tight text-white">DECOY <span className="text-[#2EE6D6]">IQ</span></h1>
        <p className="mt-3 max-w-2xl text-lg text-slate-300">
          ¿Cuánto valor táctico puede generar un receptor <em>sin recibir el balón</em>? DECOY IQ convierte datos de tracking en
          métricas geométricas interpretables sobre proximidad defensiva, desplazamiento de defensores y espacio liberado para compañeros.
        </p>
        <button onClick={() => go('explorer')} className="mt-6 rounded-lg bg-[#FFC933] px-5 py-2.5 text-sm font-bold text-black hover:brightness-110">
          Analizar jugadas →
        </button>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="¿Qué es el Decoy Value Index (DVI)?">
          <p className="text-sm leading-relaxed text-slate-300">
            Indicador <strong>experimental</strong> de 0 a 100 que resume el valor táctico indirecto <em>observable</em> de un receptor
            que no fue el objetivo: combina cuatro componentes normalizados (proximidad defensiva potencial, arrastre defensivo,
            espacio liberado para el objetivo y para otros compañeros) con pesos fijados por el equipo.
          </p>
          <p className="mt-2 text-xs text-slate-400">
            No es una probabilidad de éxito, no demuestra causalidad y no es una métrica oficial de la NFL. Detecta coincidencias espaciales,
            no intenciones ni la mirada de los defensores.
          </p>
        </Card>
        <Card title="Estado de los datos">
          {loading && <Loading what="estado de los datos" />}
          {error && <Notice kind="error">No se pudo consultar la API: {error}</Notice>}
          {data && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <Stat label="Partidos" value={data.n_games} />
                <Stat label="Jugadas" value={data.n_plays_with_tracking} />
                <Stat label="Filas tracking" value={data.tracking_rows.toLocaleString('es-MX')} />
              </div>
              {data.notes.map((n) => <Notice key={n} kind={data.has_data ? 'info' : 'warn'}>{n}</Notice>)}
              {data.files.length > 0 && (
                <ul className="space-y-1 text-xs text-slate-400">
                  {data.files.map((f) => (
                    <li key={f.archivo}><span className="font-mono text-slate-200">{f.archivo}</span> · {f.tipo} · {f.filas.toLocaleString('es-MX')} filas</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
