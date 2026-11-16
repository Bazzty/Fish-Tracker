# Formato común Tracker ⇄ Validador

**Versión 1 · propuesta del equipo Tracker (pendiente de aceptación por un equipo del Validador).**
Ejemplo sintético y válido (cajas inventadas, un tubo con 0 peces): [`docs/ejemplo_formato/`](ejemplo_formato/), generado con `scripts/generar_ejemplo_formato.py`. Comprobar una carpeta: `uv run tracker validar <carpeta>`.

Una ejecución = una carpeta con 5 archivos, UTF-8, CSV con encabezado y separador coma, punto decimal.

| Archivo | Contenido |
|---|---|
| `meta.json` | Video, perfil, pesos, fps, tamaño, conteo final por canal |
| `canales.json` | Tubos marcados y su zona de conteo |
| `detecciones.csv` | Peces detectados, cuadro a cuadro (antes del seguimiento) |
| `trayectorias.csv` | Peces seguidos: la misma caja con su ID y canal |
| `conteos.csv` | Un evento por pez contado |

**Convenciones.** `cuadro` empieza en 0 y `tiempo_s = cuadro / fps` (segundos desde el inicio del video). Coordenadas en píxeles del video original, origen arriba a la izquierda (`x` a la derecha, `y` hacia abajo). `canal` es el `id` de un canal de `canales.json`. `id` es único **dentro de su canal** y no se reutiliza; la clave de un pez es `(canal, id)`.

## `meta.json`
```json
{"version": 1, "video": "ejemplo_sintetico.mp4", "perfil": "base", "pesos": "weights/best.pt",
 "fps": 10.0, "ancho": 1280, "alto": 720, "cuadros": 60, "solo_detectar": false,
 "conteos": {"canal_1": 2, "canal_2": 0}, "total": 2}
```
`conteos` trae **todos los canales activos**; un tubo sin peces vale `0`. Debe coincidir con la cantidad de filas de cada canal en `conteos.csv`. Se admiten campos extra (p. ej. `nota`).

## `canales.json`
```json
{"version": 1, "video": {"archivo": "ejemplo_sintetico.mp4", "ancho": 1280, "alto": 720},
 "canales": [{"id": "canal_1", "caja": [100, 0, 500, 720], "nombre": "Tubo 1",
              "linea_a": 0.4, "linea_b": 0.6, "activo": true, "forma": "rect"}]}
```
**Origen (por ahora):** los canales vienen del ground truth. El Validador entrega `canales.json` como archivo aparte y el Tracker lo usa tal cual (`uv run tracker procesar --canales canales.json …`, o **Cargar canales…** en la GUI para revisarlo); el Tracker no los redefine. El `canales.json` de la carpeta de salida es una copia de ese archivo.

`caja` = `[x1, y1, x2, y2]` en píxeles. `linea_a` y `linea_b` son fracciones del alto del canal medidas desde su borde superior (`0 ≤ a < b ≤ 1`); los peces avanzan de arriba hacia abajo. `forma` es siempre `"rect"` en la versión 1.

## Columnas
- `detecciones.csv`: `cuadro, tiempo_s, canal, x1, y1, x2, y2, conf` — `canal` queda vacío si el centro de la caja cae fuera de todo canal.
- `trayectorias.csv`: `cuadro, tiempo_s, canal, id, x1, y1, x2, y2, conf, cx, cy` — `cx, cy` es el centro de la caja.
- `conteos.csv`: `canal, id, cuadro, tiempo_s, conteo` — `cuadro` es el instante en que el pez se contó; `conteo` es el acumulado del canal tras ese evento.

## Regla de conteo
Define cuándo se escribe una fila en `conteos.csv`. Se aplica por canal, sobre `trayectorias.csv`.

- **Qué es un pez:** una trayectoria `(canal, id)`. Cuenta **como máximo una vez** en todo el video.
- **Posición del pez:** el centro de su caja (`cx`, `cy`). Los peces avanzan de arriba hacia abajo (`y` crece).
- **Líneas del canal:** `y_A = y1 + linea_a · (y2 − y1)` e `y_B = y1 + linea_b · (y2 − y1)`, con `y1` e `y2` de la `caja` del canal.
- **Línea base (`perfil: base`):** el pez cuenta en el primer cuadro en que su centro llega a la línea A desde arriba, es decir, cuando en el cuadro anterior en que se vio estaba sobre A (`cy < y_A`) y en este está en A o bajo ella (`cy ≥ y_A`).
- **Variante (`perfil: variante`, histéresis):** el pez queda «armado» al estar sobre A y cuenta recién cuando su centro llega a la línea B (`cy ≥ y_B`). Si oscila entre A y B no se cuenta de nuevo. Se descartan las trayectorias más cortas que un mínimo de cuadros, y un ID nuevo que continúa a otro perdido hereda su estado, para no contarlo dos veces.
- **Qué no cuenta:** los movimientos hacia arriba (no suman ni restan), un pez que aparece por primera vez ya bajo la línea sin haberla cruzado, y las detecciones sin trayectoria o fuera de todo canal.
- **Momento del evento:** el `cuadro` y el `tiempo_s` son los del cuadro en que se cumple la regla.
- **Tubo sin peces:** conteo `0` en `meta.json`, sin filas en `conteos.csv`.
- **Referencia del Validador:** el conteo de referencia (tracker perfecto) se obtiene aplicando la regla de la línea base a las trayectorias etiquetadas, con los canales del ground truth (el mismo `canales.json` que recibe el Tracker). Si el curso define otra regla de conteo, esa reemplaza a esta y se sube `version`.

## Para corregir conteos (Validador)
Para sumar o quitar un pez basta agregar o borrar su fila de `conteos.csv` y actualizar `meta.json` (`conteos`, `total`). El Tracker lee la carpeta con `tracker.formato.leer`, que la valida antes.

## Propuesta versión 2: un archivo de trayectorias por canal
**Estado:** requisito del profesor (un tracker por canal), pendiente de revisión por el equipo del Validador. El Tracker la implementará una vez acordada.

**Qué cambia.** `trayectorias.csv` se reemplaza por un archivo por canal activo, `trayectorias_<id>.csv` (p. ej. `trayectorias_canal_1.csv`), con las mismas columnas. El resto queda igual:

```
salida/
  meta.json                 # version: 2
  canales.json              # copia del archivo del ground truth
  detecciones.csv           # global
  trayectorias_canal_1.csv
  trayectorias_canal_2.csv
  conteos.csv               # global
```

- Hay un archivo por **cada canal activo**; un tubo sin peces trae solo el encabezado.
- La columna `canal` se mantiene (redundante con el nombre del archivo) para que los archivos se puedan concatenar sin perder el dato.
- `conteos.csv` y `detecciones.csv` siguen globales: los conteos se leen juntos para todos los tubos, y las detecciones son un dato intermedio que incluye filas sin canal.

**Por qué.** Sigue el criterio de MOTChallenge (TrackEval, py-motmetrics): un archivo de tracks por secuencia, y las métricas (MOTA, IDF1, HOTA) se calculan por secuencia. Cada canal actúa como una secuencia, ya que los `id` son únicos dentro de su canal, así que el Validador compara un archivo del Tracker contra uno del ground truth por tubo.

**Para decidir con el Validador.**
1. ¿El ground truth también se entrega por canal, con el mismo nombre de archivo?
2. ¿Se adopta el orden de columnas de MOT (`cuadro, id, x1, y1, w, h, conf`) para usar TrackEval sin conversión, o se mantienen las actuales?

**Cambios en el Tracker.** `formato.exportar`, `leer` y `validar` (buscar `trayectorias_*.csv` y exigir uno por canal activo), el ejemplo de `docs/ejemplo_formato/` y `VERSION` en `meta.json`.

## Cambios
Todo cambio de columnas sube `version` y se avisa a ambos equipos.
