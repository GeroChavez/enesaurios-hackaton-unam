import { useEffect, useState } from 'react'
import { useApi } from './api'
import Home from './pages/Home'
import Explorer from './pages/Explorer'
import Tactical from './pages/Tactical'
import DviPage from './pages/Dvi'
import NovaPage from './pages/Nova'
import type { Dvi, PlayDetail, Tracking } from './types'
import { Loading, Notice } from './ui'

type Page = 'home' | 'explorer' | 'tactical' | 'dvi' | 'nova'
const NAV: { id: Page; label: string; needsPlay: boolean }[] = [
  { id: 'home', label: 'Inicio', needsPlay: false },
  { id: 'explorer', label: 'Explorador', needsPlay: false },
  { id: 'tactical', label: 'Campo táctico', needsPlay: true },
  { id: 'dvi', label: 'Análisis DVI', needsPlay: true },
  { id: 'nova', label: 'Amazon Nova', needsPlay: true },
]

export default function App() {
  const [page, setPage] = useState<Page>('home')
  const [sel, setSel] = useState<{ game: string; play: string } | null>(null)
  const [receiver, setReceiver] = useState<string | null>(null)

  const base = sel ? `plays/${sel.game}/${sel.play}` : null
  const detail = useApi<PlayDetail>(base)
  const tracking = useApi<Tracking>(base ? `${base}/tracking` : null)
  const dvi = useApi<Dvi>(base ? `${base}/dvi` : null)

  useEffect(() => {
    const first = dvi.data?.receivers.find((r) => r.dvi != null)
    setReceiver(first?.id ?? null)
  }, [dvi.data])

  const pick = (game: string, play: string) => { setSel({ game, play }); setPage('tactical') }

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-[#070b14]/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-4 py-3">
          <button onClick={() => setPage('home')} className="text-xl font-black tracking-tight">DECOY <span className="text-[#2EE6D6]">IQ</span></button>
          <nav className="flex flex-wrap gap-1">
            {NAV.map((n) => (
              <button key={n.id} onClick={() => setPage(n.id)} disabled={n.needsPlay && !sel}
                title={n.needsPlay && !sel ? 'Primero selecciona una jugada' : undefined}
                className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-30 ${page === n.id ? 'bg-white/15 text-white' : 'text-slate-400 hover:text-white'}`}>
                {n.label}
              </button>
            ))}
          </nav>
          {sel && <span className="ml-auto font-mono text-xs text-slate-400">Partido {sel.game} · Jugada {sel.play}</span>}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        {page === 'home' && <Home go={() => setPage('explorer')} />}
        {page === 'explorer' && <Explorer onPick={pick} />}
        {sel && page !== 'home' && page !== 'explorer' && (detail.error || tracking.error) && (
          <Notice kind="error">{detail.error ?? tracking.error}</Notice>
        )}
        {sel && page === 'tactical' && (detail.loading || tracking.loading) && <Loading what="la jugada" />}
        {sel && page === 'tactical' && detail.data && tracking.data && (
          <Tactical detail={detail.data} tracking={tracking.data} dvi={dvi.data} selected={receiver} setSelected={setReceiver} />
        )}
        {sel && page === 'dvi' && (
          <DviPage dvi={dvi.data} loading={dvi.loading} error={dvi.error} selected={receiver} setSelected={setReceiver} />
        )}
        {sel && page === 'nova' && <NovaPage key={`${sel.game}-${sel.play}`} game={sel.game} play={sel.play} dvi={dvi.data} selected={receiver} />}
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-500">
        DECOY IQ es un proyecto de hackathon. El DVI es un indicador experimental del equipo, no una métrica oficial de la NFL ni una medida causal.
      </footer>
    </div>
  )
}
