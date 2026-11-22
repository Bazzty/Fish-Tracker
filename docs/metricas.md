# Vocabulario de métricas y resultados

Qué significa cada columna y cada campo que escriben las herramientas de seguimiento y conteo.

## Evaluación del seguimiento (`metricas_<grupo>.csv` / `.json`)

Las escribe `uv run tracker evaluar-seguimiento` en `outputs/evaluacion_seguimiento/<detector>/`. Comparan lo que hizo el tracker con las trayectorias etiquetadas de DAT-02. Una caja del tracker cuenta como el mismo pez del etiquetado si se solapan al menos un 50 % (IoU ≥ 0,5).

| Columna del CSV | Nombre técnico (clave en el JSON) | Qué significa | Mejor si |
|---|---|---|---|
| TRACKER | — | Tracker evaluado (nombre de su YAML). | — |
| SEQUENCE | — | Secuencia evaluada; `TOTAL` suma todas las secuencias. | — |
| PERCENTAGE OF CORRECT IDs | IDF1 (`IDF1`) | De todo el tiempo que se ve cada pez, en qué porcentaje el tracker le mantuvo **su mismo ID**. Es la principal para no contar dos veces al mismo pez. | alto |
| TIMES ID CHANGED | ID switches, IDSW (`IDSW`) | Cuántas veces un mismo pez **cambió de ID** (lo perdió y le dio un número nuevo, o le cambió el ID con otro pez). | bajo |
| OVERALL TRACKING ACCURACY (MOTA) | MOTA (`MOTA`) | Nota global del seguimiento: descuenta peces no encontrados, cajas de más y cambios de ID, sobre el total de cajas etiquetadas. Puede ser negativa. | alto |
| — (solo en el JSON) | MOTP (`MOTP`) | Qué tan bien ajustadas están las cajas que sí acertaron (solape promedio con la caja etiquetada). | alto |
| EXTRA BOXES | Falsos positivos, FP (`FP`) | Cajas del tracker que **no corresponden a ningún pez** etiquetado. | bajo |
| MISSING BOXES | Falsos negativos, FN (`FN`) | Cajas de peces etiquetados que el tracker **no encontró**. Si es alto, casi siempre es el detector. | bajo |
| Frag | Fragmentaciones (`Frag`) | Veces que el seguimiento de un pez **se corta y se retoma** (aunque recupere el mismo ID). | bajo |
| MT | Mostly tracked (`MT`) | Peces **seguidos casi siempre**: al menos el 80 % del tiempo que aparecen. | alto |
| ML | Mostly lost (`ML`) | Peces **casi nunca seguidos**: menos del 20 % del tiempo que aparecen. | bajo |
| TOTAL FISHES | `peces_gt` | Peces distintos que hay según el etiquetado. | — |
| FISHES COUNTED BY TRACKER | `ids_tracker` | IDs distintos que creó el tracker. Si es mayor que TOTAL FISHES, inventó IDs para peces que ya tenía. | ≈ TOTAL FISHES |
| COUNT TRACKER | `conteo_tracker` | Peces que **contó el sistema** con la regla del perfil (línea simple en `base`, dos líneas en `variante`). | ≈ COUNT REFERENCE |
| COUNT REFERENCE | `conteo_referencia` | El **conteo real**: la línea simple aplicada a las trayectorias etiquetadas. | — |
| COUNT ERROR | `error_conteo` | Diferencia entre lo contado y lo real: `|COUNT TRACKER − COUNT REFERENCE|`. Es la comparación principal del plan. En TOTAL, `|suma contada − suma real|`. | 0 |

Con `--oraculo` el tracker recibe las cajas etiquetadas en vez del detector: lo que falle ahí es culpa del tracker, no del detector.

## Seguimiento y conteo de un video (`seguimiento.json`, `conteo.json`)

Los escribe `uv run tracker procesar`:

```
outputs/seguimiento/<detector>_<tracker>/<secuencia>/seguimiento.json
outputs/conteo/<detector>_<tracker>/<secuencia>/<regla>/conteo.json      (+ los 5 archivos del formato común)
```

`<detector>`: archivo de pesos (`yolo26`, `best`). `<tracker>`: `bytetrack`, `botsort`, `botsort_reid`, `ocsort` o `deepsort`. `<regla>`: `linea_simple` o `dos_lineas`.

**Común a los dos (`corrida`):** `fecha`, `secuencia`, `video`, `perfil`, `modelo` (nombre, pesos, confianza mínima, IoU del NMS), `seguimiento` (nombre, tipo, YAML y parámetros), `fps`, `ancho`, `alto`, `cuadros`; y `canales`: cada tubo con su `caja` en píxeles y sus líneas `linea_a` y `linea_b` (fracción del alto y `y` en píxeles).

| `seguimiento.json` | Qué significa |
|---|---|
| `resumen.<canal>.peces_seguidos` | Peces (IDs) seguidos en ese tubo. |
| `peces_por_canal.<canal>[]` | Un pez: `id`, `primer_cuadro`, `ultimo_cuadro`, `cuadros_vistos` y su `trayectoria`. |
| `trayectoria[]` | Cada cuadro en que se vio: `cuadro` (desde 0), `imagen` (archivo de la secuencia), `tiempo_s`, `caja` (`x1, y1, x2, y2, ancho, alto` en píxeles), `centro` (`x, y`) y `confianza` del detector. |

| `conteo.json` | Qué significa |
|---|---|
| `regla_de_conteo` | Regla usada (`linea_simple` o `dos_lineas`) y sus parámetros (mínimo de cuadros, herencia). |
| `conteo_real` | De dónde sale el conteo real (DAT-02), o por qué no hay. |
| `resultado.por_canal.<canal>` | `contados_por_el_sistema`, `conteo_real` y `error` = diferencia absoluta. |
| `resultado.total` | Lo mismo sumando todos los tubos. |
| `eventos[]` | Cada pez contado: `canal`, `id`, `cuadro`, `imagen`, `tiempo_s` y `conteo` (acumulado del tubo tras contarlo). |

## Reglas de conteo

- **Línea simple (`linea_simple`, perfil `base`):** un pez cuenta una vez cuando su centro pasa de estar sobre la línea A a estar en ella o bajo ella.
- **Dos líneas (`dos_lineas`, histéresis, perfil `variante`):** el pez se «arma» al verse sobre la línea A y cuenta al llegar a la línea B. No cuenta trayectorias de menos de `min_cuadros` cuadros, y un ID nuevo que aparece donde debería estar otro perdido hace poco (su última posición más su velocidad por los cuadros perdidos) hereda su estado.
