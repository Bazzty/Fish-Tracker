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
- **Referencia del Validador:** el conteo de referencia (tracker perfecto) se obtiene aplicando la regla de la línea base a las trayectorias etiquetadas, con los mismos canales. Si el curso define otra regla de conteo, esa reemplaza a esta y se sube `version`.

## Para corregir conteos (Validador)
Para sumar o quitar un pez basta agregar o borrar su fila de `conteos.csv` y actualizar `meta.json` (`conteos`, `total`). El Tracker lee la carpeta con `tracker.formato.leer`, que la valida antes.

## Propuesta (no vigente): archivos por canal
Hoy los CSV traen todos los canales juntos y se separan por la columna `canal`. Si se necesitan archivos por tubo, las alternativas son:

1. **Sin cambios:** filtrar por `canal` al analizar (p. ej. `df[df.canal == "canal_1"]`).
2. **Carpeta por canal:** `salida/canal_1/{detecciones,trayectorias,conteos}.csv`, con `meta.json` y `canales.json` globales. Rompe `leer` y `validar`, que deben recorrer las subcarpetas; sube `version`.
3. **Copias adicionales por canal:** se mantienen los 5 archivos y se agregan `trayectorias_canal_1.csv`, etc. Compatible con la versión 1, pero duplica datos que el Validador debería comprobar que coincidan.

Recomendación del Tracker: opción 3 si el requisito es solo entregar por tubo; la 2 solo si se rediseña el formato. Requiere acuerdo de ambos equipos.

## Cambios
Todo cambio de columnas sube `version` y se avisa a ambos equipos.
