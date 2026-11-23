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
| `--salida` | Guarda todos los archivos en una sola carpeta. |

Archivos generados con el perfil por defecto:

```
outputs/seguimiento/yolo26_ocsort/seq_00015/seguimiento.json      trayectoria de cada pez, por tubo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/conteo.json     conteo del sistema, conteo real y error por tubo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/anotado.mp4     video con tubos, líneas, IDs y conteo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/                además, los 5 archivos del formato común
```

Las rutas siguen el esquema `outputs/<operación>/<detector>_<tracker>/<secuencia>/`. En el video, la línea A es amarilla, la línea B es naranja y cada pez cambia a verde cuando se cuenta. Para regenerarlo: `uv run python scripts/video_conteo.py <carpeta del conteo> --video <video>`.

#### 3. Evaluar el seguimiento contra DAT-02

`evaluar-seguimiento` ejecuta el detector una vez por secuencia y aplica cada tracker sobre las mismas detecciones. Con `--oraculo`, las detecciones se reemplazan por las cajas etiquetadas, lo que permite distinguir los errores del tracker de los del detector.

```powershell
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml --oraculo
uv run python scripts/video_seguimiento.py seq_00015 --tracker ocsort
```

Val se usa para comparar y ajustar. La medición final, con el tracker de la variante, se hace una sola vez en test ([resultado](resultados/tablas/seguimiento_test.md)):

```powershell
uv run tracker evaluar-seguimiento --conjunto test
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

```powershell
uv run python scripts/barrido_tracker.py --aplicar
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
| Entrenamiento y evaluación del detector | `src/entrenamiento/entrenar.py`, `evaluar.py`, `experimentos.py` |

### Resultados

Todas las cifras son de secuencias que el modelo no vio al entrenar. Val sirvió para elegir y test se usó una sola vez, al final.

| Qué | Línea base (YOLO11 + ByteTrack) | Variante (YOLO26 + OC-SORT + dos líneas) | Detalle |
|---|---|---|---|
| Detector, mAP@50 en val | 0,9436 | 0,9916 | [yolo11_vs_yolo26.md](resultados/tablas/yolo11_vs_yolo26.md) |
| Detector, recall en val | 0,8904 | 0,9673 | [yolo11_vs_yolo26.md](resultados/tablas/yolo11_vs_yolo26.md) |
| Detector, mAP@50 en test | — | 0,9913 | [yolo11_vs_yolo26.md](resultados/tablas/yolo11_vs_yolo26.md) |
| Conteo en val (8 secuencias) | — | 135 de 137 peces, IDF1 93,0 % | [comparacion_trackers.md](resultados/tablas/comparacion_trackers.md) |
| **Conteo en test (9 secuencias)** | — | **131 de 132 peces, IDF1 93,2 %** | [seguimiento_test.md](resultados/tablas/seguimiento_test.md) |

Cómo se eligió cada pieza:

- **Detector:** YOLO26n con DAT-01 ([experimentos_yolo26.md](resultados/tablas/experimentos_yolo26.md)). Se compararon n y s y dos versiones de datos; quedaron empatados y ganó el n por ser más liviano y rápido. También se comprobó yolo26s a 100 épocas y lr0 0,01 en lugar de 0,001, sin mejora.
- **Tracker:** OC-SORT, elegido en val entre cinco trackers y 28 combinaciones de parámetros ([comparacion_trackers.md](resultados/tablas/comparacion_trackers.md)).

Límite: train, val y test vienen de la misma cámara. Las cifras valen para este montaje; en otra instalación hay que validar de nuevo.

### Estructura del repositorio

```
Fish-Tracker/
├── README.md
├── pyproject.toml / uv.lock
├── configs/           config.yaml (parámetros), split.yaml (partición), perfiles/, trackers y JSON de tubos
├── src/
│   ├── comun.py       rutas, semilla, dispositivo y data.yaml compartidos
│   ├── tracker/       la aplicación: pipeline, detector, seguimiento, conteo, salidas, formato y gui/
│   └── entrenamiento/ entrenar, evaluar y experimentos del detector
├── scripts/           partición, videos, referencia de conteo y barrido de trackers
├── weights/           best.pt (YOLO11, base) y yolo26.pt (variante), cada uno con su ficha .yaml
├── resultados/        métricas (.json), curvas de entrenamiento (results.csv) y tablas/
├── docs/              comandos, métricas, formato común y plan
├── issues/            problemas encontrados
├── lab15/             archivo del Lab 15 (diseño, partición antigua y resultados)
├── data/              datos privados (no se versiona)
└── outputs/           videos y corridas (no se versiona)
```

### Requisitos

[uv](https://docs.astral.sh/uv/), git y, para entrenar, una GPU NVIDIA con driver reciente (`nvidia-smi` debe mostrar CUDA 12.8 o más). `uv sync` instala PyTorch con CUDA 12.8 en Windows y Linux (necesario para la serie RTX 50) y desde PyPI en macOS. Clonar en una ruta corta, sin espacios ni OneDrive. Si `uv sync` actualiza `uv.lock`, subir ese archivo.

### Reproducibilidad

- Semilla 42, `deterministic=True` y optimizador SGD explícito (con `optimizer: auto` Ultralytics ignora `lr0`).
- `evaluar.py` usa el `imgsz` guardado en los pesos y umbrales fijos (`conf 0.001`, `iou 0.7`, lote 16).
- `plots=False`: Ultralytics no guarda imágenes del dataset en `resultados/`. Los datos no salen de `data/`.
- Los comandos para entrenar y medir el detector están en [`docs/comandos.md`](docs/comandos.md).
- Entrega: `git archive --format=zip --prefix=Fish-Tracker/ -o Fish-Tracker.zip HEAD` (incluye solo lo versionado: sin `data/`, `.venv/` ni `outputs/`).

El material del Lab 15 (diseño original, partición antigua y sus resultados) está en [`lab15/README.md`](lab15/README.md).
