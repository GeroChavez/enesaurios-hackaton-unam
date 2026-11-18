import { useEffect, useState } from 'react'

// Todas las llamadas usan rutas relativas SIN diagonal inicial (regla del hackathon).
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`api/${path}`, init)
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try {
      const j = await r.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j)
    } catch { /* cuerpo no JSON */ }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

export function useApi<T>(path: string | null): { data: T | null; error: string | null; loading: boolean } {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: !!path })
  useEffect(() => {
    if (!path) { setState({ data: null, error: null, loading: false }); return }
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    api<T>(path)
      .then((d) => alive && setState({ data: d, error: null, loading: false }))
      .catch((e: Error) => alive && setState({ data: null, error: e.message, loading: false }))
    return () => { alive = false }
  }, [path])
  return state
}
