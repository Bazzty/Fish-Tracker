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
# Solo el detector (usa el cuadro completo como un solo tubo)
uv run tracker inferir --video VIDEO.mp4 --salida outputs/inferencia

# Flujo completo: detectar, seguir y contar
uv run tracker procesar --video VIDEO.mp4 --canales CANALES.json --salida outputs/resultado

# Revisar que la salida cumpla el formato
uv run tracker validar outputs/resultado
```

- `--canales` es el JSON de tubos que guarda la interfaz. Para un solo tubo del tamaño del cuadro (1456 × 1088) existe `configs/canales_cuadro_completo.json`.
- `--perfil` elige la configuración: `base` (por defecto) o `variante` (pendiente de la semana 2).
- Si el video o el JSON no existen, el comando termina con `[ERROR] ...` y no deja archivos a medias.

```bash
# Comparar ByteTrack y BoT-SORT contra DAT-02 📂
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml
# Con las cajas etiquetadas en vez del detector, para separar fallas del tracker de fallas del detector
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml --oraculo
```

## 3. Scripts (`scripts/`)

| Script | Qué hace |
|---|---|
| `secuencia_a_video.py` 📂 | Arma un `.mp4` desde las imágenes de una secuencia, porque no hay videos originales. |
| `video_conteo.py` | Dibuja tubos, línea A, cajas con ID y conteo sobre una corrida de `procesar`. |
| `video_seguimiento.py` 📂 | Dibuja caja, ID y ruta de cada pez, a partir de `evaluar-seguimiento`. |
| `conteo_referencia.py` 📂 | Aplica la regla de conteo a las trayectorias etiquetadas (el conteo correcto) y lo compara con el del tracker. |
| `preparar_split.py` 📂 | Escribe los dos `data.yaml` de entrenamiento y la tabla de cuadros por conjunto. |
| `generar_ejemplo_formato.py` | Regenera `docs/ejemplo_formato/` con datos sintéticos. **Sobrescribe esos archivos.** |

```bash
# De una secuencia a un video con el conteo dibujado 📂
uv run python scripts/secuencia_a_video.py seq_00015
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales configs/canales_cuadro_completo.json --salida outputs/seq_00015
uv run python scripts/video_conteo.py outputs/seq_00015 --video outputs/videos/seq_00015.mp4

# Comparar el conteo del tracker con la referencia (usar el MISMO JSON de tubos en ambos) 📂
uv run python scripts/conteo_referencia.py --seq seq_00015 --canales configs/canales_cuadro_completo.json --comparar outputs/seq_00015

# Referencia de conteo de val y test; con --guardar escribe configs/conteo_real.yaml 📂
uv run python scripts/conteo_referencia.py
uv run python scripts/conteo_referencia.py --guardar

# Video del seguimiento (bytetrack o botsort) 📂
uv run python scripts/video_seguimiento.py seq_00015 --tracker botsort

# Preparar el split de entrenamiento 📂
uv run python scripts/preparar_split.py
```

## 4. Detector: entrenar y medir

```bash
# Medir el detector (mAP@50, precisión, recall) 📂
uv run python src/evaluar.py --split val          # validación: guarda logs/evaluacion_val_best.json
uv run python src/evaluar.py                      # test (usar una sola vez, al final)

# Probar el entrenamiento con 1 época; no toca weights/ 📂
uv run python src/entrenar.py --nombre prueba --epocas 1
```

La línea base de YOLO11 en la validación nueva es mAP@50 **0,9436** ([tabla](tablas/map50_yolo11_val.md)).

## 5. Git: sincronizar con el equipo

```bash
git fetch && git switch develop && git pull       # traer lo último de develop
git switch -c nombre-de-la-rama                   # rama nueva para un cambio
```
