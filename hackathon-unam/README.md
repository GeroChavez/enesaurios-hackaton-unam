# DECOY IQ

**Hackathon NFL × Amazon · Side Quest Querétaro · ENES Juriquilla, UNAM**

Plataforma de análisis táctico que cuantifica el **valor indirecto de los receptores que no reciben el balón**.

> ¿Cuánto valor táctico puede generar un receptor sin recibir el balón?

## Estado del proyecto (leer primero)

- **Qué es:** DECOY IQ estima, con geometría sobre el tracking, el valor táctico indirecto de los receptores que **no** reciben el balón (índice experimental DVI). **Para quién:** analistas y cuerpos técnicos que quieran ver qué hace un receptor cuando no es el objetivo. **Cómo verlo:** Explorador → elegir partido y pase → Campo táctico → Análisis DVI.
- **Hallazgo principal:** aún **no hay un hallazgo validado**. El motor está escrito y revisado, pero no se ha ejecutado con pandas/FastAPI sobre los datos reales (el entorno de desarrollo no podía instalar paquetes). Lo que sí está medido con los CSV reales (Python estándar) es la viabilidad: ver «Auditoría del dataset».
- **Datos:** `data/raw/data/` dentro de esta carpeta (126 CSV, 825 MB, formato Big Data Bowl 2021). El script oficial `--entregar` empaqueta esta carpeta completa e incluye siempre `data/` sin importar su tamaño (avisa si el zip supera 500 MB: confirmar con los organizadores). Los CSV no se modifican.
- **No ejecutado todavía:** backend con FastAPI/pandas/NumPy, `pytest`, `vite build`, TypeScript completo y la integración con Bedrock. Ver «Verificación».

## Auditoría del dataset (reproducible)

```sh
python -m backend.tools.audit_dataset      # solo biblioteca estándar, ~25 s, lee data/ sin modificarlo
```

Resultado sobre los 122 partidos (7 565 pases: C 4 620, I 2 755, IN 190):

| Medida | Pases | % |
|---|---|---|
| Receptor objetivo inferido (nombre en la descripción vs. corredores de ruta PFF) | 7 230 | 95,6 |
| DVI calculable (objetivo + snap + lanzamiento + ventana ≥ 5 cuadros + balón) | 7 207 | 95,3 |
| Con evento de llegada del pase (`pass_arrived` y similares) | 419 | 5,5 |

Validación cruzada del objetivo inferido: en los 396 pases con evento de llegada, el corredor de ruta más cercano al balón en ese cuadro coincide con el objetivo inferido en 387 (97,7 %). Es una comprobación parcial (solo pases con ese evento), no una validación completa.

Nota sobre dos cifras que circularon (7 048 y 7 230): 7 048 era el resultado de la primera versión de la inferencia, que solo reconocía «to X»; 7 230 es el resultado actual, tras añadir «intended for X» (las intercepciones pasaron de 1 a 183 con objetivo). El valor vigente es 7 230.

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

Indicador **experimental** del equipo, de 0 a 100, para receptores que **no** fueron objetivo. No es una probabilidad de éxito, no demuestra causalidad y no es una métrica oficial de la NFL. **Ningún parámetro está calibrado con datos** (σ, pesos, saturaciones, desplazamiento mínimo): son decisiones a priori del equipo, sin validación contra resultados ni expertos. Detalle completo en `GET api/methodology` y en la pantalla *Análisis DVI*.

Ventana: del snap (`ball_snap`/`autoevent_ballsnap`) al lanzamiento (`pass_forward`/`autoevent_passforward`). Sin snap, sin lanzamiento o sin objetivo identificado, la jugada es **no calculable** y la API informa el motivo. Núcleo de proximidad `K(d) = exp(-d²/(2σ²))`, σ = 3 yd. Para el receptor R y los defensores j (rol PFF *Coverage*), `a_j` es el promedio de `K(d_Rj)` en la ventana.

| Componente | Qué mide | Unidad | Saturación | Peso |
|---|---|---|---|---|
| Proximidad defensiva potencial | defensores-equivalentes cerca de R | def.-equiv. | 1.0 | 0.25 |
| Arrastre defensivo (seguimiento) | proyección del desplazamiento de los defensores cercanos a R sobre la dirección de la ruta de R, menos el promedio de toda la defensa (requiere que R se desplace ≥ 2 yd) | yd | 4 | 0.25 |
| Espacio para el objetivo | aumento de distancia al objetivo de defensores compartidos con R | yd | 2 | 0.30 |
| Espacio para otros compañeros | lo mismo, promediado sobre otros receptores | yd | 2 | 0.20 |

`DVI = 100 · Σ wᵢcᵢ / Σ wᵢ` sobre los componentes calculables, con `cᵢ = clip(valor/saturación, 0, 1)`; se reporta la cobertura de pesos usada.

**Auditoría de doble contabilización.** Una versión previa del arrastre medía el alejamiento de los defensores respecto a la zona del balón; como esa zona está casi sobre el objetivo, equivalía al espacio para el objetivo. Se redefinió para no usar objetivo ni balón. Persiste una correlación esperable (los cuatro componentes salen de las posiciones de los mismos defensores y `a_j` se reutiliza como peso); no se ha cuantificado.

**Observado vs. inferido.** Observados: posiciones, eventos, roles PFF (`pff_role`). Inferido: el receptor objetivo (el dataset no lo trae); la interfaz y la API lo marcan (`target_inferred`).

**Aproximación del balón.** El punto de llegada del pase (zona de referencia) solo existe como evento en ≈ 5 % de los pases; en los demás se aproxima con la posición del balón en el cuadro de menor distancia al objetivo tras el lanzamiento. Esa zona **solo se dibuja en el campo; no entra en el DVI**.

**Grafo dinámico** (`analytics/graph.py`): nodos = receptores, pasador y defensores; aristas ofensivo–defensor si `d ≤ 8 yd` con peso `K(d)`; la variación `Δd` entre dos cuadros clasifica cada arista como se aleja / se acerca / estable. Endpoint: `GET api/plays/{game}/{play}/graph`.

## Instalación y ejecución (comandos oficiales de la plantilla)

Versiones fijas: Python 3.12.12, uv 0.11.19, Node 22.23.1, npm 10.x. El instalador crea `.venv` y un Node portátil en `.hackathon/.tools/` sin tocar el sistema; **no ejecutes `pip install` ni `npm install` por tu cuenta**.

**macOS / Linux** (desde `hackathon-unam/`):
```sh
sh .hackathon/setup.sh                 # instala todo (o reutiliza lo ya instalado)
sh .hackathon/setup.sh --check         # valida el entorno
cp .env.example .env                   # OPCIONAL: solo para Bedrock; pega las llaves del workshop
.venv/bin/python -m pytest backend/tests
.venv/bin/uvicorn backend.main:app --reload          # terminal 1: API en http://localhost:8000
export PATH="$PWD/.hackathon/.tools/node/bin:$PATH"  # terminal 2: Node portátil
cd dashboard && npm run dev                          # Vite; /api se redirige a :8000
```

**Windows** (PowerShell, desde `hackathon-unam\`; en CMD omite el `.\` inicial):
```powershell
.\.hackathon\setup.cmd                 # instala todo
.\.hackathon\setup.cmd --check
copy .env.example .env                  # OPCIONAL: solo para Bedrock
.\.venv\Scripts\python.exe -m pytest backend\tests
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload     # terminal 1
$env:Path = "$PWD\.hackathon\.tools\node;$env:Path"                  # terminal 2: Node portátil
cd dashboard; npm run dev
```

Abre **`http://localhost:5173`** (no `127.0.0.1`). Producción local (un solo puerto): con el Node portátil en el PATH, `cd dashboard && npm run build`; luego `uvicorn backend.main:app` sirve `dashboard/dist` y la API en `http://localhost:8000`.

**Entrega:** `sh .hackathon/setup.sh --entregar` (Windows: `.\.hackathon\setup.cmd --entregar`). Genera `entrega-hackathon-unam-<fecha>.zip` junto a esta carpeta; no incluye `.env`, `.venv`, `node_modules` ni `.hackathon`, e incluye `data/` completa.

## Uso

1. **Inicio**: estado de los datos y explicación del DVI.
2. **Explorador**: elige un partido; por defecto lista solo pases (C, I, IN) con su descripción; elige una jugada.
3. **Campo táctico**: SVG con jugadores, balón, rutas, aviso si el objetivo es inferido, reproducción cuadro a cuadro y saltos al lanzamiento/llegada. Clic en un receptor para ver defensores a ≤ 5 yd.
4. **Análisis DVI**: resumen automático (sin IA), DVI, aporte por componente, comparación entre receptores, evolución temporal, metodología y limitaciones.
5. **Amazon Nova** (opcional): explicación en lenguaje natural de las métricas ya calculadas. Sin Bedrock, el resumen automático del paso 4 cubre la explicación.

API: `GET /health`, `GET api/data/status`, `api/games`, `api/plays`, `api/plays/{game}/{play}`, `…/tracking`, `…/dvi`, `…/graph`, `api/methodology`, `api/nova/status`, `POST api/plays/{game}/{play}/nova`.

## Amazon Bedrock (opcional)

Solo Amazon Bedrock con Nova, vía Strands Agents y boto3. Modelo: `BEDROCK_MODEL_ID` (por defecto `us.amazon.nova-pro-v1:0`); región: `AWS_REGION` (por defecto `us-east-1`). El cliente se crea solo con la región; las credenciales las resuelve boto3 (rol en AWS, `.env` en local). Nunca se escriben llaves en el código. Si Bedrock falla o no está configurado, la pantalla lo indica y el resto funciona. Nova solo recibe métricas ya calculadas.

## Verificación

Estado real de cada comprobación (ninguna afirmación sin ejecución):

| Comprobación | Estado |
|---|---|
| `python -m backend.tools.audit_dataset` (biblioteca estándar, datos reales) | **Ejecutada**: cifras de «Auditoría del dataset» |
| Reconocimiento de columnas y tipos de tabla en los 126 CSV (`schema.py`) | **Ejecutada** con Python estándar sobre las cabeceras reales |
| Reglas del script oficial sobre rutas `/` del dashboard, README y contenido del zip | **Ejecutadas** importando las funciones de `.hackathon/setup.py`: sin rutas con `/`, README presente (sin imagen: aviso), `data/` incluida |
| Sintaxis de todo el Python (`ast`) y de los `.tsx` (`tsc` global, sin tipos de React) | Ejecutada; no sustituye a `vite build` |
| `pytest backend/tests` (datos sintéticos, no de la NFL) | **Pendiente** (faltan pandas/FastAPI en el entorno de desarrollo) |
| Backend con FastAPI/pandas/NumPy sobre los CSV reales y rendimiento | **Pendiente** |
| `npm run build` / `tsc` con tipos de React | **Pendiente** |
| Amazon Bedrock / Nova | **Pendiente** (requiere llaves del workshop) |

Para ejecutar lo pendiente use los comandos de «Instalación y ejecución», más `sh .hackathon/setup.sh --entregar` al final.

## Limitaciones conocidas

- Nada del backend con pandas/FastAPI se ha ejecutado todavía; el rendimiento con 122 archivos (825 MB) está por medir. Cada partido se indexa solo cuando se consulta.
- El receptor objetivo es inferido por nombre (95,6 % de los pases). La coincidencia con el balón en la llegada (97,7 %) solo cubre los pases con ese evento; el resto no está validado jugada por jugada.
- La zona de referencia del balón es una aproximación y no entra en el DVI.
- El DVI usa solo el tramo snap→lanzamiento; no modela bloqueos, coberturas asignadas (hay `pff_passCoverage` pero no se usa), mirada ni orientación corporal.
- Los pesos, saturaciones y σ del DVI **no están calibrados** ni validados contra resultados reales.
- El tracking proviene de un solo formato (BDB 2021); otros esquemas se reconocen solo si sus columnas coinciden con los alias de `schema.py`.
- El zip de entrega pesará ≈ 825 MB por los datos (el script avisa a partir de 500 MB).
