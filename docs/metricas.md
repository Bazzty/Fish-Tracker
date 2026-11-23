# Vocabulario de métricas y resultados

Este documento describe cada columna y cada campo que generan las herramientas de seguimiento y conteo.

## Evaluación del seguimiento

`uv run tracker evaluar-seguimiento` escribe en `outputs/evaluacion_seguimiento/<detector>/` los archivos `metricas_<grupo>_<regla>.csv` y `metricas_<grupo>_<regla>.json`. En ellos se compara el resultado de cada tracker con las trayectorias etiquetadas de DAT-02. Una caja del tracker se considera el mismo pez que una caja etiquetada cuando ambas se superponen al menos en un 50 % (IoU ≥ 0,5).

| Columna del CSV | Nombre técnico (clave en el JSON) | Significado | Valor deseable |
|---|---|---|---|
| TRACKER | — | Tracker evaluado (nombre de su archivo YAML). | — |
| SEQUENCE | — | Secuencia evaluada. La fila `TOTAL` agrega todas las secuencias. | — |
| PERCENTAGE OF CORRECT IDs | IDF1 (`IDF1`) | Porcentaje del tiempo en que el tracker mantiene **el mismo ID** para cada pez. Es la métrica más relacionada con no contar dos veces un mismo pez. | Alto |
| TIMES ID CHANGED | Cambios de identidad, IDSW (`IDSW`) | Número de veces que un mismo pez **cambia de ID**, ya sea porque el tracker lo pierde y le asigna uno nuevo o porque intercambia el ID con otro pez. | Bajo |
| OVERALL TRACKING ACCURACY (MOTA) | MOTA (`MOTA`) | Exactitud global del seguimiento: descuenta los peces no encontrados, las cajas sobrantes y los cambios de ID respecto del total de cajas etiquetadas. Puede ser negativa. | Alto |
| — (solo en el JSON) | MOTP (`MOTP`) | Ajuste de las cajas correctamente asociadas: superposición promedio con la caja etiquetada. | Alto |
| EXTRA BOXES | Falsos positivos, FP (`FP`) | Cajas del tracker que **no corresponden a ningún pez** etiquetado. | Bajo |
| MISSING BOXES | Falsos negativos, FN (`FN`) | Cajas de peces etiquetados que el tracker **no encontró**. Un valor alto suele indicar fallas del detector. | Bajo |
| Frag | Fragmentaciones (`Frag`) | Número de veces que el seguimiento de un pez **se interrumpe y se retoma**, aunque conserve el ID. | Bajo |
| MT | *Mostly tracked* (`MT`) | Peces **seguidos la mayor parte del tiempo**: al menos el 80 % de los cuadros en que aparecen. | Alto |
| ML | *Mostly lost* (`ML`) | Peces **seguidos muy poco tiempo**: menos del 20 % de los cuadros en que aparecen. | Bajo |
| TOTAL FISHES | `peces_gt` | Número de peces distintos según el etiquetado. | — |
| FISHES COUNTED BY TRACKER | `ids_tracker` | Número de IDs distintos que creó el tracker. Si supera a TOTAL FISHES, el tracker asignó IDs nuevos a peces que ya seguía. | Cercano a TOTAL FISHES |
| COUNT TRACKER | `conteo_tracker` | Peces **contados por el sistema** con la regla del perfil (línea simple en `base`, dos líneas en `variante`). | Cercano a COUNT REFERENCE |
| COUNT REFERENCE | `conteo_referencia` | **Conteo real**: la regla de línea simple aplicada a las trayectorias etiquetadas. | — |
| COUNT ERROR | `error_conteo` | Diferencia absoluta entre el conteo del sistema y el real: \|COUNT TRACKER − COUNT REFERENCE\|. Es la comparación principal del plan. En la fila `TOTAL`, se calcula sobre las sumas. | 0 |

`<grupo>` es el conjunto evaluado (`val`, `test`) o las secuencias indicadas con `--seq`; `<regla>` es `linea_simple` o `dos_lineas`; `<detector>` es el nombre de los pesos (`yolo26`, `best`) u `oraculo`.

Con `--oraculo`, el tracker recibe las cajas etiquetadas en lugar de las del detector. Los errores que persisten en ese caso se deben al tracker y no al detector.

## Seguimiento y conteo de un video

`uv run tracker procesar` genera los siguientes archivos:

```
outputs/seguimiento/<detector>_<tracker>/<secuencia>/seguimiento.json
outputs/conteo/<detector>_<tracker>/<secuencia>/<regla>/conteo.json     (junto a los 5 archivos del formato común)
```

`<detector>` es el nombre de los pesos (`yolo26`, `best`); `<tracker>` es `bytetrack`, `botsort`, `botsort_reid`, `ocsort` o `deepsort`; `<regla>` es `linea_simple` o `dos_lineas`.

### Campos comunes

| Campo | Significado |
|---|---|
| `corrida.fecha`, `corrida.secuencia`, `corrida.video`, `corrida.perfil` | Fecha de la ejecución, secuencia, video y perfil usados. |
| `corrida.modelo` | Detector: nombre, archivo de pesos, confianza mínima e IoU del NMS. |
| `corrida.seguimiento` | Tracker: nombre, tipo, archivo YAML y parámetros. |
| `corrida.fps`, `corrida.ancho`, `corrida.alto`, `corrida.cuadros` | Propiedades del video. |
| `canales[]` | Cada tubo: `id`, `nombre`, `caja` en píxeles, `activo` y sus líneas `linea_a` y `linea_b` (fracción del alto y coordenada `y` en píxeles). |

### `seguimiento.json`

| Campo | Significado |
|---|---|
| `resumen.<canal>.peces_seguidos` | Número de peces (IDs) seguidos en el tubo. |
| `peces_por_canal.<canal>[]` | Cada pez: `id`, `primer_cuadro`, `ultimo_cuadro`, `cuadros_vistos` y `trayectoria`. |
| `trayectoria[]` | Cada cuadro en que se vio el pez: `cuadro` (desde 0), `imagen` (archivo de la secuencia), `tiempo_s`, `caja` (`x1`, `y1`, `x2`, `y2`, `ancho`, `alto`, en píxeles), `centro` (`x`, `y`) y `confianza` del detector. |

### `conteo.json`

| Campo | Significado |
|---|---|
| `regla_de_conteo` | Regla usada (`linea_simple` o `dos_lineas`) y sus parámetros (mínimo de cuadros y herencia de estado). |
| `conteo_real` | Origen del conteo real (DAT-02) o el motivo por el que no está disponible. |
| `resultado.por_canal.<canal>` | `contados_por_el_sistema`, `conteo_real` y `error` (diferencia absoluta). |
| `resultado.total` | Los mismos valores, sumando todos los tubos. |
| `eventos[]` | Cada pez contado: `canal`, `id`, `cuadro`, `imagen`, `tiempo_s` y `conteo` (acumulado del tubo tras contarlo). |

## Reglas de conteo

- **Línea simple** (`linea_simple`, perfil `base`): un pez se cuenta una sola vez, cuando el centro de su caja pasa de estar sobre la línea A a estar en ella o bajo ella.
- **Dos líneas** (`dos_lineas`, histéresis, perfil `variante`): el pez queda armado al verse sobre la línea A y se cuenta al alcanzar la línea B. No se cuentan las trayectorias vistas en menos de `min_cuadros` cuadros. Un ID nuevo que aparece donde debería estar otro perdido recientemente (según su última posición y su velocidad) hereda su estado.
