# DECOY IQ

**Hackathon NFL × Amazon · Side Quest Querétaro · ENES Juriquilla, UNAM**

Plataforma de análisis táctico que cuantifica el **valor indirecto de los receptores que no reciben el balón**.

> ¿Cuánto valor táctico puede generar un receptor sin recibir el balón?

## Estado del proyecto (leer primero)

- El dataset real (126 CSV, formato Big Data Bowl 2021: 122 archivos de tracking por partido + `games`, `plays`, `players`, `pffScoutingData`) está en `data/raw/data/` en la raíz del repositorio. El backend busca `data/` primero en la raíz del proyecto (`hackathon-unam/`) y, si no existe, en la raíz del repositorio. **Para la entrega con `--entregar`, `data/` debe estar dentro de `hackathon-unam/`** (decisión pendiente del equipo; no se movió ningún CSV).
- El motor se ajustó al esquema real inspeccionando los archivos (ver «Esquema del dataset»).
- **El entorno de desarrollo no pudo instalar paquetes**, así que el backend (FastAPI/pandas/numpy), `vite build` y `pytest` **no se han ejecutado**. Lo verificado: la lógica de esquema (`schema.py`) y la inferencia del objetivo (`targets.py`) se ejecutaron con Python estándar sobre los CSV reales; el resto solo pasó revisión de sintaxis. Ver «Verificación».

## Esquema del dataset (verificado con los archivos reales)

| Archivo | Clave | Uso en DECOY IQ |
|---|---|---|
| `tracking/tracking_<gameId>.csv` (122) | `gameId, playId, nflId, frameId` | posiciones x,y, `s`, `a`, `dis`, `team`, `playDirection`, `event`; el balón son filas con `nflId` vacío y `team=football` |
| `plays.csv` | `gameId, playId` | descripción, posesión, `passResult` (C, I, IN, S, R). **No incluye receptor objetivo** |
| `pffScoutingData.csv` | `gameId, playId, nflId` | `pff_role` (Pass, Pass Route, Pass Block, Pass Rush, Coverage) y alineación |
| `players.csv` | `nflId` | nombre y posición oficial |
| `games.csv` | `gameId` | semana, equipos |

Hechos medidos en los datos: cada archivo de tracking tiene un solo partido y las filas de cada jugada son contiguas (permite leer una jugada sin cargar el archivo); `time` solo tiene resolución de segundos, por eso el intervalo entre cuadros se estima con `dis/s` (≈ 0.1 s); los eventos de llegada del pase existen en pocas jugadas (≈ 4 % en la muestra), por eso la zona de referencia usa la trayectoria del balón (ver DVI).

**Receptor objetivo:** se infiere comparando el nombre de la descripción («to C.Godwin», «intended for C.Lamb») con los corredores de ruta (`Pass Route`) de esa jugada; solo se acepta una coincidencia única. En todos los pases C/I/IN del dataset se resuelve ≈ 96 % (7 230 de ≈ 7 565). Es una inferencia, no un campo oficial.

**Viabilidad medida (Python estándar, 21 de 122 partidos, muestra sistemática):** de 1 292 pases, 1 226 (95 %) tienen snap, lanzamiento, objetivo y balón, es decir, DVI calculable. Mediana: 29 cuadros entre snap y lanzamiento, 4 receptores no objetivo y 7 defensores en cobertura por jugada. Sacks, scrambles y pases sin destinatario nombrado quedan sin DVI (se informa el motivo).

## Problema y propuesta de valor

Las estadísticas tradicionales solo premian al receptor que atrapa. Un receptor puede, además, atraer defensores, desplazarlos o liberar espacio para un compañero. DECOY IQ convierte datos de tracking en métricas geométricas interpretables que revelan esa contribución, **separando coincidencia espacial de causalidad**.

## Arquitectura

```
backend/
  main.py            app FastAPI, GET /health, carga de .env (procedimiento oficial), sirve dashboard/dist si existe
  core/              config (rutas), schema (alias de columnas), data_store (lectura eficiente de CSV)
  analytics/         roles, tracks (matrices frame×jugador), geometry (cinemática), decoy (DVI), graph (grafo dinámico)
  services/          play_service (orquesta datos+motor), nova_service (Amazon Nova opcional)
  routers/api.py     endpoints bajo /api
  tests/             pruebas con datos SINTÉTICOS (pytest)
dashboard/           React + TypeScript + Vite + Tailwind 3 + Recharts
data/                CSV del evento (solo lectura; no se versiona aquí)
```

Lectura de datos: al primer uso se indexa cada CSV de tracking **por bloques de 500 000 filas** (solo columnas clave) para saber en qué filas está cada jugada; después cada consulta lee únicamente las filas de esa jugada. No se escribe nada en disco.

## Stack

Python 3.12.12 · FastAPI 0.115.14 · Uvicorn 0.34.3 · Pydantic 2.11.7 · pandas 2.2.3 · NumPy 2.1.3 · Node 22.23.1 · React 18.3.1 · Vite 5.4.21 · TypeScript 5.7.3 · Tailwind 3.4.19 · Recharts 3.10.1 · Strands Agents 1.64.0 / boto3 1.44.0 (opcional). Sin dependencias adicionales.

## Decoy Value Index (DVI)

Indicador **experimental** del equipo, de 0 a 100, para receptores que **no** fueron objetivo. No es una probabilidad de éxito, no demuestra causalidad y no es una métrica oficial de la NFL. Detalle completo (fórmulas, unidades, normalización, limitaciones) en `GET api/methodology` y en la pantalla *Análisis DVI*.

Ventana: del snap al lanzamiento (`ball_snap`/`autoevent_ballsnap` a `pass_forward`/`autoevent_passforward`); requiere objetivo y lanzamiento identificados. Núcleo de proximidad `K(d) = exp(-d²/(2σ²))`, σ = 3 yd. Para el receptor R y los defensores j, `a_j` es el promedio de `K(d_Rj)` en la ventana.

| Componente | Qué mide | Unidad | Saturación | Peso |
|---|---|---|---|---|
| Proximidad defensiva potencial | defensores-equivalentes cerca de R | def.-equiv. | 1.0 | 0.25 |
| Arrastre defensivo | alejamiento de la zona de balón Z (punto de la trayectoria del balón más cercano al objetivo tras el lanzamiento, o posición en `pass_arrived` si existe) de los defensores cercanos a R, menos el movimiento defensivo promedio | yd | 4 | 0.25 |
| Espacio para el objetivo | aumento de distancia al objetivo de defensores compartidos con R | yd | 2 | 0.30 |
| Espacio para otros compañeros | lo mismo, promediado sobre otros receptores | yd | 2 | 0.20 |

`DVI = 100 · Σ wᵢcᵢ / Σ wᵢ` sobre los componentes calculables, con `cᵢ = clip(valor/saturación, 0, 1)`. Los pesos y saturaciones son criterio del equipo, no se ajustaron con datos. La «atención defensiva» es **proximidad geométrica**: los datos no incluyen mirada.

**Grafo dinámico** (`analytics/graph.py`): nodos = receptores, pasador y defensores; aristas ofensivo–defensor si `d ≤ 8 yd` con peso `K(d)`; la variación `Δd` entre dos cuadros clasifica cada arista como se aleja / se acerca / estable. Endpoint: `GET api/plays/{game}/{play}/graph`.

## Instalación

```sh
sh .hackathon/setup.sh            # crea .venv e instala dependencias fijadas
cp .env.example .env              # opcional, solo para Bedrock
# los CSV ya están en data/raw/data/ (ver «Estado del proyecto» sobre su ubicación)
```

## Ejecución

Desarrollo (dos terminales, desde la raíz del proyecto `hackathon-unam/`):

```sh
.venv/bin/uvicorn backend.main:app --reload          # API en :8000
cd dashboard && npm run dev                          # Vite; /api se redirige a :8000
```

Producción local: `cd dashboard && npm run build` y luego `.venv/bin/uvicorn backend.main:app`; el backend sirve `dashboard/dist` y la API en la misma URL.

## Uso

1. **Inicio**: estado de los datos y explicación del DVI.
2. **Explorador**: filtra por partido y busca en la descripción (si existe tabla de jugadas); elige una jugada.
3. **Campo táctico**: SVG con jugadores, rutas, reproducción cuadro a cuadro y saltos al lanzamiento/llegada. Clic en un receptor para ver defensores a ≤ 5 yd.
4. **Análisis DVI**: DVI, aporte por componente, comparación entre receptores, evolución temporal, metodología y limitaciones.
5. **Amazon Nova**: explicación en lenguaje natural de las métricas ya calculadas.

API: `GET /health`, `GET api/data/status`, `api/games`, `api/plays`, `api/plays/{game}/{play}`, `…/tracking`, `…/dvi`, `…/graph`, `api/methodology`, `api/nova/status`, `POST api/plays/{game}/{play}/nova`.

## Amazon Bedrock (opcional)

Solo Amazon Bedrock con Nova, vía Strands Agents y boto3. Modelo: `BEDROCK_MODEL_ID` (por defecto `us.amazon.nova-pro-v1:0`); región: `AWS_REGION` (por defecto `us-east-1`). El cliente se crea solo con la región; las credenciales las resuelve boto3 (rol en AWS, `.env` en local). Nunca se escriben llaves en el código. Si Bedrock falla o no está configurado, la pantalla lo indica y el resto funciona. Nova solo recibe métricas ya calculadas.

## Verificación

```sh
.venv/bin/python -m pytest backend/tests     # datos sintéticos; NO son datos de la NFL
cd dashboard && npm run build
sh .hackathon/setup.sh --check
```

## Limitaciones conocidas

- Nada de esto se ha ejecutado con pandas/FastAPI/Vite todavía (ver «Estado del proyecto»); el rendimiento con 122 archivos (826 MB) está por medir. Cada partido se indexa solo cuando se consulta.
- El receptor objetivo es inferido por nombre (≈ 96 % de los pases); puede haber errores de coincidencia que no se han auditado jugada por jugada.
- La zona Z es una aproximación (no hay evento de llegada en la mayoría de jugadas). Para pases incompletos, el punto de mínima distancia balón–objetivo puede no coincidir con el aterrizaje real.
- El DVI usa solo el tramo previo al lanzamiento; no modela bloqueos, coberturas asignadas (hay `pff_passCoverage` pero no se usa), mirada ni orientación corporal.
- El tracking proviene de un solo formato (BDB 2021); otros esquemas se reconocen solo si sus columnas coinciden con los alias de `schema.py`.
- Pesos y saturaciones del DVI no están calibrados con datos.
- Sin validación estadística frente a resultados de jugadas.
