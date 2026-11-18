export interface DataFile {
  archivo: string
  tipo: string
  filas: number
  columnas: string[]
  columnas_reconocidas: Record<string, string>
  calidad: Record<string, number> | null
}
export interface DataStatus {
  has_data: boolean
  n_games: number
  n_plays_with_tracking: number
  tracking_rows: number
  files: DataFile[]
  notes: string[]
}
export interface GameItem { game_id: string; n_plays: number; week?: number | null; game_date?: string | null; home_team?: string | null; visitor_team?: string | null }
export interface PlayItem {
  game_id: string; play_id: string; has_tracking: boolean
  description?: string | null; quarter?: number | null; down?: number | null; yards_to_go?: number | null
  possession?: string | null; defensive_team?: string | null; pass_result?: string | null; game_clock?: string | null
}
export interface PlayList { total: number; limit: number; offset: number; items: PlayItem[]; descripciones_disponibles: boolean }

export type PlayerClass = 'objetivo' | 'pasador' | 'receptor_no_objetivo' | 'ofensiva_otro' | 'defensor' | 'defensor_presion' | 'desconocido'
export interface PlayerInfo { id: string; name: string | null; position: string | null; side: string; role_raw: string | null; cls: PlayerClass; basis: string }
export interface Events {
  start_frame: number; throw_frame: number | null; throw_source: string | null
  arrival_frame: number | null; ball_land: { x: number; y: number } | null
}
export interface PlayDetail {
  game_id: string; play_id: string; info: Record<string, unknown>; game_info: Record<string, unknown>
  players: PlayerInfo[]; events: Events; time: { dt_s: number; source: string }
  data_quality: { frames: number; jugadores: number; celdas_sin_dato: number; celdas_totales: number }
  meta: Record<string, unknown>; notes: string[]
}
export interface TrackPlayer { id: string; name: string | null; position: string | null; side: string; class: PlayerClass; x: (number | null)[]; y: (number | null)[] }
export interface Tracking { game_id: string; play_id: string; frames: number[]; t_s: number[]; events: Events; players: TrackPlayer[]; orientation_normalized: boolean }

export interface DviComponent {
  key: string; label: string; unit: string; weight: number; ref: number
  raw: number | null; normalized: number | null; note: string | null; n_beneficiarios: number | null
}
export interface DviPoint { frame: number; t_s: number; dvi: number | null; [k: string]: number | null }
export interface NearDefender { id: string; name: string | null; position: string | null; peso_proximidad: number; distancia_media_yd: number; distancia_minima_yd: number }
export interface DviReceiver {
  id: string; name: string | null; position: string | null; dvi: number | null; weight_coverage?: number; reason?: string
  components?: DviComponent[]; series?: DviPoint[]; closest_defenders?: NearDefender[]; kinematics?: Record<string, number | null>
}
export interface Dvi {
  available: boolean; reason: string | null; target_id: string | null; receivers: DviReceiver[]; warnings: string[]
  window: { start_frame: number; end_frame: number; throw_frame: number | null; throw_source: string | null; dt_s: number; dt_source: string; arrival_frame: number | null }
  zone?: { x: number; y: number } | null; zone_source?: string; notes?: string[]
}
export interface Methodology {
  nombre: string; estado: string; escala: string; ventana: string; pesos: string; doble_conteo: string; no_calculable: string; solo_no_objetivo: string
  nucleo: { sigma_yd: number; formula: string }
  componentes: { key: string; label: string; unit: string; formula: string; measures: string; limitation: string; weight: number; ref: number }[]
}
export interface NovaResult { available: boolean; text?: string; error?: string; reason?: string | null; model_id?: string; region?: string; via?: string }
