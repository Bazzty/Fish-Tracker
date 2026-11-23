# Fish-Tracker

Sistema que detecta, sigue y cuenta salmones en video.
USS-ICIFH001 · Inteligencia Artificial · Lab 15 (base) y Solemne 3 (Tracker, cliente Duotek).

## Tracker (Solemne 3)

Aplicación de escritorio que, a partir de un video, permite marcar los tubos (canales) y contar los salmones que pasan por cada uno sin contar dos veces el mismo pez. Los resultados se intercambian con el Validador mediante un [formato común](docs/formato_comun.md).

Documentos relacionados:

- [`docs/comandos.md`](docs/comandos.md): referencia de comandos y del archivo de tubos.
- [`docs/metricas.md`](docs/metricas.md): significado de cada métrica y de cada campo de los resultados.
- [`docs/plan.md`](docs/plan.md): tareas, responsables y estado.

### Instalación

Los comandos se ejecutan desde la raíz del repositorio. FFmpeg se instala como dependencia del proyecto (`imageio-ffmpeg`), por lo que los videos se generan en H.264 sin pasos adicionales.

```powershell
uv sync
```

### Perfiles

Un perfil define el detector, el tracker y la regla de conteo. Se selecciona con `--perfil`; si se omite, se usa `variante`.

| Perfil | Detector | Tracker | Regla de conteo | Uso |
|---|---|---|---|---|
| `variante` (por defecto) | YOLO26 (`weights/yolo26.pt`) | OC-SORT (`configs/tracker_variante.yaml`) | Dos líneas | Configuración final del sistema. |
| `base` | YOLO11 (`weights/best.pt`) | ByteTrack (`configs/bytetrack.yaml`) | Línea simple | Línea base del plan, para comparar. |

La regla de conteo puede cambiarse sin cambiar de perfil con `--conteo linea_simple` o `--conteo dos_lineas`, y el tracker con `--tracker configs/<tracker>.yaml`.

### Reglas de conteo

- **Línea simple.** Un pez, identificado por su canal y su ID, se cuenta una sola vez: cuando el centro de su caja pasa de estar sobre la línea A del tubo a estar en ella o bajo ella. Un pez que sube, o que aparece por primera vez bajo la línea, no se cuenta.
- **Dos líneas (histéresis).** El pez queda armado al verse sobre la línea A y se cuenta al alcanzar la línea B; así, una caja que oscila en torno a una línea no suma de más. Además:
  - no se cuentan las trayectorias vistas en menos de 5 cuadros;
  - un ID nuevo que aparece donde debería estar otro perdido recientemente (según su última posición y su velocidad) hereda su estado, de modo que un pez fragmentado por el tracker no se pierde ni se cuenta dos veces.

Los parámetros se definen en `configs/perfiles/variante.yaml`, y la especificación completa, en el [formato común](docs/formato_comun.md#regla-de-conteo).

### Flujo de trabajo

#### 1. Preparar los datos de entrenamiento

`scripts/preparar_split.py` lee `configs/split.yaml`, única fuente de la partición (el criterio de selección está documentado en ese archivo), y genera dos archivos de datos con la misma validación y la misma prueba:

- `runs/data_dat01.yaml`: entrenamiento solo con DAT-01.
- `runs/data_lab15_dat01.yaml`: entrenamiento con Lab 15 y DAT-01.

También genera la tabla [`resultados/tablas/cuadros_por_split.md`](resultados/tablas/cuadros_por_split.md). El resultado es determinista: con los mismos datos, siempre es el mismo.

```powershell
uv run python scripts/preparar_split.py
```

#### 2. Contar los salmones de un video

Como el repositorio no incluye los videos originales, primero se arma uno a partir de las imágenes de `data/`. Luego, `procesar` ejecuta el detector, el seguimiento por tubo y el conteo, genera el video anotado e imprime la ubicación de cada archivo.

```powershell
uv run python scripts/secuencia_a_video.py seq_00015
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos
```

| Opción | Descripción |
|---|---|
| `--canales` | Archivo JSON con los tubos y sus líneas, por ruta o por nombre de un archivo de `configs/`. Formato y uso: [`docs/comandos.md`, sección 3](docs/comandos.md#3-tubos-y-líneas-de-conteo-json-de-canales). |
| `--seq` | Nombre de la secuencia. Por defecto se toma del nombre del video. Si la secuencia tiene trayectorias en DAT-02, `conteo.json` incluye el conteo real y el error por tubo. |
| `--perfil`, `--tracker`, `--conteo` | Ver [Perfiles](#perfiles). |
| `--sin-video` | Omite el video anotado. |
| `--fps` | Cuadros por segundo del video anotado. Por defecto, los del video de entrada. Solo cambia la velocidad de reproducción, no el conteo. |
| `--salida` | Guarda todos los archivos en una sola carpeta. |

Todos los videos se escriben en H.264 con el FFmpeg de `imageio-ffmpeg`. `secuencia_a_video.py` usa por defecto 10 cuadros por segundo (`conteo.fps_cuadros` de `configs/config.yaml`), que es la frecuencia de captura de las secuencias, y acepta `--fps` para cambiarla. Esos fps pasan a ser los del video de entrada y determinan `tiempo_s` en `seguimiento.json` y `conteo.json`, pero no el número de peces contados.

Archivos generados con el perfil por defecto:

```
outputs/seguimiento/yolo26_ocsort/seq_00015/seguimiento.json      trayectoria de cada pez, por tubo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/conteo.json     conteo del sistema, conteo real y error por tubo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/anotado.mp4     video con tubos, líneas, IDs y conteo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/                además, los 5 archivos del formato común
```

Las rutas siguen el esquema `outputs/<operación>/<detector>_<tracker>/<secuencia>/`. En el video, la línea A es amarilla, la línea B es naranja y cada pez cambia a verde cuando se cuenta. Para regenerarlo: `uv run python scripts/video_conteo.py <carpeta del conteo> --video <video>`, con `--fps` opcional.

#### 3. Evaluar el seguimiento contra DAT-02

`evaluar-seguimiento` ejecuta el detector una vez por secuencia y aplica cada tracker sobre las mismas detecciones. Con `--oraculo`, las detecciones se reemplazan por las cajas etiquetadas, lo que permite distinguir los errores del tracker de los del detector.

```powershell
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml --oraculo
uv run python scripts/video_seguimiento.py seq_00015 --tracker ocsort
```

Los resultados se guardan en `outputs/evaluacion_seguimiento/<detector>/` (`yolo26`, `best` u `oraculo`):

- `<secuencia>/<tracker>.txt`: trayectorias en formato MOT; `video_seguimiento.py` deja a su lado `<tracker>.mp4`.
- `metricas_<grupo>_<regla>.csv` y `.json` (por ejemplo, `metricas_val_dos_lineas.csv`): por secuencia y en total, IDF1, cambios de ID, MOTA, cajas sobrantes y faltantes, y el error de conteo respecto de la referencia, que es la comparación principal del plan. El significado de cada columna está en [`docs/metricas.md`](docs/metricas.md).

| Tracker | Archivo | Biblioteca | Observaciones |
|---|---|---|---|
| ByteTrack | `configs/bytetrack.yaml` | Ultralytics | Tracker del perfil `base`. |
| BoT-SORT | `configs/botsort.yaml` | Ultralytics | |
| BoT-SORT con ReID | `configs/botsort_reid.yaml` | Ultralytics | Compara la apariencia de cada pez con los pesos del detector; requiere la imagen y es más lento. |
| OC-SORT | `configs/ocsort.yaml` | `trackers` | Requiere Python 3.11 o superior. |
| DeepSORT | `configs/deepsort.yaml` | `deep-sort-realtime` | Compara la apariencia con una red MobileNet; requiere la imagen y es más lento. |

#### 4. Elegir el tracker de la variante

`scripts/barrido_tracker.py` evalúa 28 combinaciones de parámetros de los cinco trackers, con el detector y con el oráculo, y las ordena por error de conteo, luego por IDF1 y luego por cambios de ID. Escribe la tabla y la decisión en [`resultados/tablas/comparacion_trackers.md`](resultados/tablas/comparacion_trackers.md). Con `--aplicar`, el ganador se copia a `configs/tracker_variante.yaml`, que es el tracker del perfil `variante`; `--rapido` omite DeepSORT y BoT-SORT con ReID, que son los más lentos.

Por defecto se usan las secuencias de val de `configs/split.yaml`; `--yaml test` usa las de test y escribe `comparacion_trackers_test.md`, sin reemplazar la tabla de val. El ganador se elige solo en val: con test, `--aplicar` no está permitido, ya que test sirve para confirmar la decisión.

```powershell
uv run python scripts/barrido_tracker.py --aplicar
uv run python scripts/barrido_tracker.py --yaml test
```

#### 5. Guardar el conteo de referencia

`scripts/conteo_referencia.py --guardar` escribe en `configs/conteo_real.yaml` el conteo de cada secuencia de validación y prueba según DAT-02, con un tubo del tamaño del cuadro y la línea A en `conteo.linea` de `configs/config.yaml`. Reemplaza el conteo manual del Lab 15.

```powershell
uv run python scripts/conteo_referencia.py --guardar
```

### Otros comandos

```powershell
uv run tracker                                                                # abre la interfaz gráfica
uv run tracker inferir --video outputs/videos/seq_00015.mp4                   # solo el detector -> outputs/deteccion/yolo26/seq_00015/
uv run tracker validar outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas     # comprueba el formato común
```

### Datos de la Solemne 3

Los datos no se versionan. Deben ubicarse en `data/` con la siguiente estructura:

```
data/
├── seq_00008/                      DAT-01 (etiquetado del curso): images/ con los cuadros y labels/ con etiquetas YOLO
├── ...
├── lab15_sec1/ ... lab15_sec6/     Lab 15 (etiquetado del profesor): misma estructura; solo se usa en entrenamiento
└── tracking/                       DAT-02 (trayectorias); ruta configurable en rutas.tracking de config.yaml
    └── seq_00015_Final/
        ├── gt/gt.txt               frame,id,x,y,w,h,conf,clase,visibilidad (formato MOT)
        └── frames.txt              frame,imagen: asocia cada frame del gt.txt con su imagen (frame 1 = _00000)
```

### Organización del código

| Componente | Ubicación |
|---|---|
| Contrato `procesar(video, canales, perfil) -> Resultados` y perfil por defecto | `src/tracker/pipeline.py` |
| Canales (tubos) y sus líneas de conteo | `src/tracker/canales.py`, `configs/canales_*.json` |
| Detector por cuadro | `src/tracker/detector.py` |
| Seguimiento por canal (un tracker por tubo) | `src/tracker/seguimiento.py`, `configs/<tracker>.yaml` |
| Conteo: línea simple y dos líneas | `src/tracker/conteo.py` |
| Carpetas de salida, `seguimiento.json` y `conteo.json` | `src/tracker/salidas.py` |
| Video anotado | `src/tracker/video.py` |
| Formato común: exportar, leer y validar | `src/tracker/formato.py` |
| Evaluación del seguimiento contra DAT-02 | `src/tracker/evaluar_seguimiento.py` |
| Interfaz gráfica | `src/tracker/gui/` |
| Perfiles | `configs/perfiles/base.yaml`, `configs/perfiles/variante.yaml` |
| Partición y archivos de datos | `configs/split.yaml`, `scripts/preparar_split.py` |
| Elección del tracker | `scripts/barrido_tracker.py`, `configs/tracker_variante.yaml` |
| Conteo de referencia | `scripts/conteo_referencia.py`, `configs/conteo_real.yaml` |
| Videos | `scripts/secuencia_a_video.py`, `scripts/video_conteo.py`, `scripts/video_seguimiento.py` |

Línea base de detección (YOLO11 del Lab 15 en la validación nueva, 8 secuencias de DAT-01): mAP@50 **0,9436** ([tabla](resultados/tablas/map50_yolo11_val.md)). YOLO26n (`weights/yolo26.pt`) llega a mAP@50 **0,9916** en la misma validación ([comparación](resultados/tablas/yolo11_vs_yolo26.md)).

> Lo que sigue (diseño, partición, reproducción y resultados) describe el **Lab 15** y su partición antigua de 6 secuencias; sus cifras no valen para la Solemne 3.
> Los scripts `entorno.py`, `grilla.py`, `contar.py`, `criterio.py`, `analisis.py` y `visualizador.py` del Lab 15 se quitaron del repositorio (siguen en el historial de git, antes del commit «chore: quitar scripts y resultados del Lab 15»). Estas secciones se conservan solo como referencia de cómo se obtuvo el detector.

## Inicio rápido

Todos los comandos se ejecutan desde la raíz del repositorio. Los datos no se incluyen: ver la sección Datos.

```powershell
uv sync
uv run python src/entrenamiento/entrenar.py --nombre prueba --epocas 1
uv run python src/entrenamiento/evaluar.py --split val
```

Qué hace cada uno: instala el entorno, entrena 1 época de prueba (no toca `weights/`) y evalúa los pesos entregados (mAP@0.5 de validación 0,9431, en la partición antigua del Lab 15). Para contar los salmones de un video se usa `uv run tracker procesar` (ver la sección Tracker).

## Diseño

```
Video → Lectura → Detector (YOLO11) → Seguimiento (ByteTrack) → Conteo (línea virtual) → Video anotado + conteo
```

| Módulo | Entra | Sale | Técnica |
|---|---|---|---|
| Lectura de video | archivo de video | cuadros, uno a uno | OpenCV `VideoCapture` |
| Detector | un cuadro | cajas con confianza (clase `fish`) | YOLO11 (Ultralytics) |
| Seguimiento | cajas de cada cuadro | cajas con ID | ByteTrack |
| Conteo | cajas con ID | número de salmones que cruzan hacia abajo | cruce de línea virtual |
| Anotación | cuadro, cajas con ID, línea, conteo | video anotado | OpenCV |

### Decisiones y fuentes

- **Detector: YOLO11, tamaños n (base) y s (comparación).** Detector de un solo pase, entrena con las etiquetas YOLO tal cual vienen y se integra con el seguimiento. Los salmones son grandes (mediana ~3,7 % de la imagen) y hay pocos por cuadro, por lo que un modelo pequeño debería bastar; la comparación n vs s lo verifica.
  Fuentes: [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11); Redmon et al., [You Only Look Once](https://arxiv.org/abs/1506.02640) (CVPR 2016, idea de detección en un solo pase).
- **Seguimiento: ByteTrack.** Asocia casi todas las cajas, incluidas las de baja confianza (el detector entrega desde 0,10), para reducir trayectorias fragmentadas. El umbral de asociación `match_thresh` se elige en validación (ver `lab15/metodologia.md`). Usa solo movimiento y cajas. No hay etiquetas de seguimiento, por lo que se elige el método más simple y explicable.
  Fuentes: Zhang et al., [ByteTrack](https://arxiv.org/abs/2110.06864); [Ultralytics Track](https://docs.ultralytics.com/modes/track/) (soporta ByteTrack, parámetros `track_high_thresh`, `track_buffer`, `match_thresh`).
- **Conteo: cruce de línea virtual.** La cámara es fija y mira desde arriba; los salmones avanzan en vertical, de arriba hacia abajo. La línea es horizontal (cruza todo el ancho del cuadro, cubre ambas vías) y está al 50 % del alto, medida desde arriba; se eligió en validación entre 40, 50 y 60 %, junto con `match_thresh` (0,8). Cada ID se cuenta una sola vez: cuando el centro de su caja cruza la línea hacia abajo o, si hubo un salto de cuadros, cuando aparece por primera vez sobre la línea o bajo ella sin subir (ver `lab15/metodologia.md`).
  Fuente: [Ultralytics Object Counting](https://docs.ultralytics.com/guides/object-counting/) (conteo con línea o región, entradas y salidas).
- **Lectura y escritura de video: OpenCV.** Fuentes: [cv::VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html) (lee video), [cv::VideoWriter](https://docs.opencv.org/4.x/dd/d9e/classcv_1_1VideoWriter.html) (guarda video).

Limitaciones: ByteTrack se evalúa en benchmarks de personas y ningún paper citado trata salmones.

## Estructura

```
Contreras-Carrera/
├── README.md
├── pyproject.toml / uv.lock
├── configs/
│   ├── config.yaml        # TODOS los parámetros: semilla, entrenamiento, grilla, conteo, criterio
│   ├── split.yaml         # partición por secuencia (única fuente)
│   ├── conteo_real.yaml   # conteo manual por secuencia (Avance 1)
│   └── bytetrack.yaml     # parámetros fijos de ByteTrack
├── src/
│   ├── comun.py           # compartido: rutas, semilla, dispositivo, data.yaml, lectura de cuadros
│   ├── tracker/           # la aplicación: pipeline, detector, seguimiento, conteo, formato
│   │   └── gui/           # interfaz de escritorio
│   └── entrenamiento/
│       ├── entrenar.py    # entrena UNA configuración del detector
│       └── evaluar.py     # mAP@0.5, mAP@0.5:0.95, precisión, recall (val o test)
├── scripts/               # preparar_split, videos de conteo y seguimiento, referencia de conteo
├── weights/               # best.pt (elegido) + best.yaml (ficha: corrida, mAP val, sha256)
├── resultados/            # corridas de entrenamiento, evaluaciones (.json) y tablas/
├── docs/                  # plan, formato común, comandos
├── lab15/                 # archivo del Lab 15: análisis del Avance 1 y metodología
└── outputs/               # videos y corridas (no se versiona)
```

## Datos

Los datos son privados: no se incluyen en el repositorio ni en la entrega.
Ubicar las 6 secuencias en `data/` con esta forma:

```
data/
├── seq_0001/
│   ├── images/    # cuadros .jpeg
│   └── labels/    # etiquetas YOLO .txt
├── ...
└── seq_0006/
```

## Partición de los datos

Por secuencia completa, definida en `configs/split.yaml`:

| Conjunto | Secuencias | Cuadros | Uso |
|---|---|---|---|
| Train | seq_0001, seq_0006 | 856 (65 %) | entrenar |
| Val | seq_0002 | 242 (18 %) | elegir hiperparámetros y modelo |
| Test | seq_0003, seq_0004, seq_0005 | 218 (17 %) | evaluación final, una sola vez |

Los cuadros vecinos son casi idénticos, por eso no se reparten por cuadro.

Metodología (métricas, criterio de éxito, plan de experimentos): ver `lab15/metodologia.md`.

## Instalación (PC con Windows y RTX 5070 Ti)

Requisitos: [uv](https://docs.astral.sh/uv/), git y driver NVIDIA reciente (`nvidia-smi` debe mostrar CUDA 12.8 o más).
Clonar en una ruta corta, sin espacios ni OneDrive (p. ej. `C:\dev\Fish-Counter`).

```powershell
uv sync
```

`uv sync` instala PyTorch con CUDA 12.8 en Windows y Linux (necesario para la serie RTX 50) y desde PyPI en macOS.
Si `uv sync` actualiza `uv.lock`, subir ese archivo al repositorio.

## Reproducir

Todos los comandos se ejecutan desde la raíz del repositorio. Los parámetros están en `configs/config.yaml`.

| Paso | Comando | Resultado |
|---|---|---|
| 0. Probar el flujo (1 época, no es la entrega) | `uv run python src/entrenamiento/entrenar.py --nombre prueba --epocas 1` | `resultados/prueba/` (no toca `weights/`) |
| 1. Entrenar la configuración entregada (R2) | `uv run python src/entrenamiento/entrenar.py --modelo yolo11n.pt --imgsz 640 --lr0 0.001 --nombre R2` | `resultados/R2/` |
| 2. Detector en test (una vez) | `uv run python src/entrenamiento/evaluar.py` | `resultados/evaluacion_test_best.json` |

La grilla de 8 corridas (`grilla.py`), el criterio de éxito (`criterio.py`) y el conteo del Lab 15 (`contar.py`) se quitaron del repositorio; sus resultados quedaron en el informe del Lab 15. El conteo del Tracker se hace con `uv run tracker procesar`.

### Resultados presentados

Pesos `weights/best.pt` (corrida R2: yolo11n, 640, lr0 0.001; sha256 `c384a62e…a2f8`).

| Qué | Comando | Valor |
|---|---|---|
| mAP@0.5 en validación | `uv run python src/entrenamiento/evaluar.py --split val` | 0,9431 |
| mAP@0.5 en test | `uv run python src/entrenamiento/evaluar.py` | 0,9685 |

Los valores de test quedan en `resultados/evaluacion_test_best.json`. La metodología del Lab 15 está en `lab15/metodologia.md`.

### Notas de reproducibilidad

- Semilla 42, `deterministic=True`, optimizador SGD explícito (con `optimizer: auto` Ultralytics ignora `lr0`).
- `evaluar.py` usa el `imgsz` guardado en los pesos y umbrales fijos (`conf 0.001`, `iou 0.7`, lote 16).
- `plots=False`: Ultralytics no guarda imágenes del dataset en `resultados/`. Los datos no salen de `data/`.
- Entrega: `git archive --format=zip --prefix=Contreras-Carrera/ -o Contreras-Carrera.zip HEAD` (incluye solo lo versionado: sin `data/`, `.venv/` ni `outputs/`).
