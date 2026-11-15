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

## Para corregir conteos (Validador)
Para sumar o quitar un pez basta agregar o borrar su fila de `conteos.csv` y actualizar `meta.json` (`conteos`, `total`). El Tracker lee la carpeta con `tracker.formato.leer`, que la valida antes.

## Cambios
Todo cambio de columnas sube `version` y se avisa a ambos equipos.
