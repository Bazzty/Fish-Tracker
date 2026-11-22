# Comandos útiles del Tracker

Todos se ejecutan desde la raíz del repositorio. Los datos (`data/`) no se versionan: los comandos marcados con 📂 los necesitan.
Para el detalle de cada parte ver el [README](../README.md) y el [plan](plan.md).

## 1. Instalar y abrir

```bash
uv sync                  # instala el entorno (FFmpeg viene incluido)
uv run tracker           # abre la interfaz: abrir video, dibujar tubos, guardar/cargar JSON
```

## 2. Comandos de `uv run tracker`

| Comando | Qué hace |
|---|---|
| `tracker` | Abre la interfaz. |
| `tracker inferir` | Solo el detector (YOLO) sobre todo el video. No sigue ni cuenta. |
| `tracker procesar` | Detector, seguimiento y conteo por tubo. Guarda los 5 archivos del [formato común](formato_comun.md). |
| `tracker validar` | Comprueba que una carpeta de resultados cumpla el formato común. |
| `tracker evaluar-seguimiento` | Compara trackers (IDF1, cambios de ID, MOTA) contra las trayectorias de DAT-02 📂. |

```bash
# Solo el detector (usa el cuadro completo como un solo tubo) -> outputs/deteccion/<detector>/<secuencia>/
uv run tracker inferir --video VIDEO.mp4

# Flujo completo: detectar, seguir y contar -> outputs/seguimiento/... y outputs/conteo/...
uv run tracker procesar --video VIDEO.mp4 --canales dos_tubos

# Lo mismo con otro tracker (bytetrack, botsort, botsort_reid, ocsort o deepsort) o con la variante
uv run tracker procesar --video VIDEO.mp4 --canales dos_tubos --tracker configs/botsort.yaml
uv run tracker procesar --video VIDEO.mp4 --canales dos_tubos --perfil base      # línea base (YOLO11)

# YOLO26 contando con una sola línea en vez de dos
uv run tracker procesar --video VIDEO.mp4 --canales dos_tubos --conteo linea_simple

# Revisar que la salida cumpla el formato
uv run tracker validar outputs/conteo/<detector>_<tracker>/<secuencia>/<regla>
```

- `--canales` es el JSON de tubos (ruta o nombre en `configs/`): formato, cómo mover las líneas y qué revisar en la [sección 3](#3-tubos-y-líneas-de-conteo-json-de-canales).
- `--perfil` elige la configuración: `variante` (YOLO26 + OC-SORT ganador del barrido + dos líneas, **por defecto**) o `base` (YOLO11 + ByteTrack + línea simple, la línea base del plan).
- Si el video o el JSON no existen, el comando termina con `[ERROR] ...` y no deja archivos a medias.

```bash
# Comparar ByteTrack, BoT-SORT (con y sin ReID), OC-SORT y DeepSORT contra DAT-02 📂
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml
# Con las cajas etiquetadas en vez del detector, para separar fallas del tracker de fallas del detector
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml --oraculo
```

## 3. Tubos y líneas de conteo (JSON de canales)

`procesar` cuenta por tubo. Los tubos y sus líneas vienen en un JSON que se pasa con `--canales` (por **ruta** o por **nombre** de un archivo de `configs/`). Lo guarda la interfaz (`uv run tracker` → dibujar tubos → guardar) o se escribe a mano.

### Formato

```json
{
  "version": 1,
  "video": {"archivo": "seq_00015.mp4", "ancho": 1456, "alto": 1088},
  "canales": [
    {"id": "canal_1", "caja": [689, 32, 1454, 1081], "nombre": "Tubo 1",
     "linea_a": 0.4, "linea_b": 0.6, "activo": true, "forma": "rect"},
    {"id": "canal_2", "caja": [0, 12, 647, 1062], "nombre": "Tubo 2",
     "linea_a": 0.4, "linea_b": 0.6, "activo": true, "forma": "rect"}
  ]
}
```

| Campo | Qué es |
|---|---|
| `version` | Siempre `1`. |
| `video` | Archivo y tamaño del video en píxeles (informativo). |
| `id` | Nombre único del tubo; es la clave en todos los resultados (`canal_1`, `canal_2`, ...). |
| `caja` | Rectángulo del tubo en píxeles del video: `[x1, y1, x2, y2]` (esquina superior izquierda e inferior derecha). Se exige `x1 < x2` e `y1 < y2`. |
| `nombre` | Etiqueta que se muestra en el video y la interfaz. |
| `linea_a` | Línea A como **fracción del alto del tubo** desde arriba (0 = borde superior, 1 = inferior). Con una línea, es la única; con dos, es donde el pez se «arma». |
| `linea_b` | Línea B (solo la usa el conteo de dos líneas): donde el pez **cuenta**. Se exige `0 ≤ linea_a < linea_b ≤ 1`. |
| `activo` | `false` = el tubo está marcado pero no se analiza. |
| `forma` | Por ahora siempre `"rect"`. |

En píxeles, cada línea queda en `y = y1 + fracción × (y2 − y1)` del tubo. Un pez cuenta en el tubo que contiene **el centro** de su caja; lo que cae fuera de todo tubo (por ejemplo, la pared entre dos tubos) no cuenta en ninguno.

### JSON incluidos (video de 1456 × 1088)

| Nombre para `--canales` | Archivo | Tubos |
|---|---|---|
| `cuadro_completo` | `configs/canales_cuadro_completo.json` | Uno, del tamaño del cuadro (líneas 0.5 y 0.6). |
| `dos_tubos` | `configs/canales_dos_tubos.json` | Mitad izquierda y mitad derecha (líneas 0.5 y 0.6). |

### Comandos

```bash
# Con un JSON incluido (por nombre)
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos

# Con un JSON de la interfaz o propio (por ruta)
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales "C:/ruta/seq_00015.canales.json"

# El video no se llama como la secuencia: decir cuál es, para tener el conteo real (DAT-02)
uv run tracker procesar --video outputs/videos/otro_nombre.mp4 --canales "C:/ruta/tubos.json" --seq seq_00015

# Una sola línea (la A) en vez de dos
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos --conteo linea_simple

# Comprobar que un JSON se lee bien (imprime cada tubo; si algo está mal, dice qué)
uv run python -c "import sys; sys.path.insert(0, 'src'); from tracker.canales import ruta_canales, cargar_canales; print(cargar_canales(ruta_canales('dos_tubos')))"
```

Un JSON copiado a `configs/` se puede pasar por nombre: `configs/canales_mis_tubos.json` → `--canales mis_tubos`.

### Mover las líneas

- Se editan `linea_a` y `linea_b` de cada tubo en el JSON (o en la interfaz). Cada tubo puede tener sus propias líneas.
- **El conteo real usa la línea A del mismo JSON:** mover la A cambia también la referencia; mover solo la B no.
- **No separar demasiado A y B:** el tracker tiene que seguir al pez entre las dos. A 10 fps un pez baja hasta ~100 px por cuadro; si se pierde entre A y B no cuenta. Con 0.5 → 0.6 (dos_tubos) son ~109 px; con 0.4 → 0.6 son ~210 px. Si en el video hay peces que cruzan A pero no cuentan, acercar las líneas (p. ej. 0.45 → 0.55).
- **`evaluar-seguimiento` y el barrido no leen el JSON de canales:** usan un tubo del tamaño del cuadro con la A en `conteo.linea` de `configs/config.yaml` (0.50) y la B 0.1 más abajo.

### Qué revisar en un JSON nuevo

- Que el **nombre del video** sea el de la secuencia (`seq_00015.mp4`) o pasar `--seq`; si no, `conteo.json` dirá «conteo real no disponible». En DAT-02 las secuencias se llaman `seq_000XX` (las `seq_000X` son del Lab 15).
- Que las cajas cubran por donde pasan los peces y que el hueco entre tubos sea solo la pared.
- Que `linea_a < linea_b` en todos los tubos.

## 4. Scripts (`scripts/`)

| Script | Qué hace |
|---|---|
| `secuencia_a_video.py` 📂 | Arma un `.mp4` desde las imágenes de una secuencia, porque no hay videos originales. |
| `video_conteo.py` | Rehace el `anotado.mp4` de una corrida de `procesar` (que ya lo genera; útil con `--sin-video`). |
| `video_seguimiento.py` 📂 | Dibuja caja, ID y ruta de cada pez, a partir de `evaluar-seguimiento`. |
| `barrido_tracker.py` 📂 | Prueba umbrales de los 5 trackers contra DAT-02 y deja la tabla y la decisión en `resultados/tablas/comparacion_trackers.md`; `--aplicar` fija el ganador en el perfil `variante`. |
| `conteo_referencia.py` 📂 | Aplica la regla de conteo a las trayectorias etiquetadas (el conteo correcto) y lo compara con el del tracker. |
| `preparar_split.py` 📂 | Escribe los dos `data.yaml` de entrenamiento y la tabla de cuadros por conjunto. |
| `generar_ejemplo_formato.py` | Regenera `docs/ejemplo_formato/` con datos sintéticos. **Sobrescribe esos archivos.** |

```bash
# De una secuencia a un video con el conteo dibujado 📂
uv run python scripts/secuencia_a_video.py seq_00015
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos
# al terminar imprime dónde quedó todo: seguimiento.json, conteo.json (contado, real y error por tubo) y anotado.mp4

# Referencia de conteo de val y test; con --guardar escribe configs/conteo_real.yaml 📂
uv run python scripts/conteo_referencia.py
uv run python scripts/conteo_referencia.py --guardar

# Video del seguimiento (bytetrack, botsort, botsort_reid, ocsort o deepsort) 📂
uv run python scripts/video_seguimiento.py seq_00015                    # tracker de la variante; --tracker botsort para otro

# Preparar el split de entrenamiento 📂
uv run python scripts/preparar_split.py
```

## 5. Detector: entrenar y medir

```bash
# Medir el detector (mAP@50, precisión, recall) 📂
uv run python src/entrenamiento/evaluar.py --split val          # validación: guarda resultados/evaluacion_val_best.json
uv run python src/entrenamiento/evaluar.py                      # test (usar una sola vez, al final)

# Probar el entrenamiento con 1 época; no toca weights/ 📂
uv run python src/entrenamiento/entrenar.py --nombre prueba --epocas 1

# Experimentos cortos YOLO26 (4 corridas, ~3 h): escribe resultados/tablas/experimentos_yolo26.md
uv run python src/entrenamiento/experimentos.py

# Entrenamiento final del ganador (100 épocas, paciencia 20)
uv run python src/entrenamiento/entrenar.py --modelo yolo26n.pt --datos dat01 --imgsz 640 --lr0 0.001 --nombre yolo26_final

# Medir YOLO26 en validación: guarda resultados/evaluacion_val_yolo26.json
uv run python src/entrenamiento/evaluar.py --pesos weights/yolo26.pt --split val
```

La línea base de YOLO11 en la validación nueva es mAP@50 **0,9436** ([tabla](../resultados/tablas/map50_yolo11_val.md)).

## 6. Git: sincronizar con el equipo

```bash
git fetch && git switch develop && git pull       # traer lo último de develop
git switch -c nombre-de-la-rama                   # rama nueva para un cambio
```
