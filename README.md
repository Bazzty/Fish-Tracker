# Fish-Tracker

Sistema que detecta, sigue y cuenta salmones en video.
USS-ICIFH001 · Inteligencia Artificial · Lab 15 (base) y Solemne 3 (Tracker, cliente Duotek).

## Tracker (Solemne 3)

Aplicación de escritorio que abre un video, deja marcar los tubos (canales) y cuenta los salmones de cada uno sin contar dos veces el mismo pez. Intercambia archivos con el Validador en un [formato común](docs/formato_comun.md). Plan, responsables y estado: [`docs/plan.md`](docs/plan.md).

### Cómo ejecutarlo

Todo se corre desde la raíz del repositorio. Los datos no se versionan: ver [Datos de la Solemne 3](#datos-de-la-solemne-3).

**1. Instalar.** FFmpeg viene incluido (`imageio-ffmpeg`): los videos salen en H.264 sin instalar nada más.

```powershell
uv sync
```

**2. Preparar el entrenamiento (split y `data.yaml`).** Lee `configs/split.yaml`, la única fuente del split (ahí está explicado cómo se eligió), y escribe `runs/data_dat01.yaml` (train solo DAT-01) y `runs/data_lab15_dat01.yaml` (train Lab 15 + DAT-01), con el mismo val y test, más la tabla [`docs/tablas/cuadros_por_split.md`](docs/tablas/cuadros_por_split.md). No hay azar: siempre sale lo mismo.

```powershell
uv run python scripts/preparar_split.py
```

**3. Contar los salmones de un video.** Arma un video desde `data/` (no hay videos originales en el repo), lo procesa (detector → seguimiento por tubo → conteo), dibuja el resultado y lo compara con la referencia de DAT-02.

```powershell
uv run python scripts/secuencia_a_video.py seq_00015
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales configs/canales_cuadro_completo.json --salida outputs/seq_00015
uv run python scripts/video_conteo.py outputs/seq_00015 --video outputs/videos/seq_00015.mp4
uv run python scripts/conteo_referencia.py --seq seq_00015 --canales configs/canales_cuadro_completo.json --comparar outputs/seq_00015
```

- `--canales` es el JSON con los tubos (`src/tracker/canales.py`): por cada tubo, su rectángulo `caja` en píxeles y la línea de conteo `linea_a` como fracción de su alto. `configs/canales_cuadro_completo.json` es un solo tubo del tamaño del cuadro (1456 × 1088) con la línea a la mitad; la interfaz de Angelo guardará los tubos reales en este mismo formato.
- Regla de conteo (línea simple): un pez `(canal, id)` suma **una sola vez**, cuando su centro pasa de estar sobre la línea A del tubo a estar en ella o bajo ella. Subir no cuenta, ni aparecer ya bajo la línea ([formato común](docs/formato_comun.md#regla-de-conteo)).
- `procesar` deja en `outputs/seq_00015/` los 5 archivos del formato común; `video_conteo.py` agrega `anotado.mp4` (tubos, línea A en amarillo, cada pez con su ID y su ruta, en verde cuando ya contó).
- `conteo_referencia.py` aplica la misma regla a las trayectorias etiquetadas (el conteo correcto) y con `--comparar` muestra tracker, referencia y error por tubo. Usar **el mismo** JSON de tubos en los dos comandos.

**4. Evaluar el seguimiento contra DAT-02.** Corre el detector una vez por secuencia y cada tracker sobre esas detecciones; escribe `outputs/evaluacion_seguimiento/<perfil>/metricas.csv` (IDF1, ID switches, MOTA, cajas de más y de menos, peces del GT y del tracker) y las trayectorias de cada tracker. Con `--oraculo` usa las cajas del GT en vez del detector, para separar fallas del tracker de fallas del detector.

```powershell
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml --oraculo
uv run python scripts/video_seguimiento.py seq_00015 --tracker botsort      # caja, ID y ruta de cada pez
```

**5. Referencia de conteo de val y test.** Escribe en `configs/conteo_real.yaml` el conteo de cada secuencia según DAT-02 (un tubo del tamaño del cuadro, línea A en `conteo.linea` de `config.yaml`). Reemplaza el conteo manual del Lab 15.

```powershell
uv run python scripts/conteo_referencia.py --guardar
```

**Otros comandos.**

```powershell
uv run tracker                                                  # abre la aplicación (interfaz en construcción)
uv run tracker inferir --video outputs/videos/seq_00015.mp4 --salida outputs/inferencia/seq_00015   # solo detector
uv run tracker validar outputs/seq_00015                        # comprueba una carpeta contra el formato común
```

### Datos de la Solemne 3

```
data/                               # no se versiona
├── seq_00008/                      # DAT-01 (etiquetado del curso): images/ con los cuadros, labels/ con YOLO .txt
├── ...
├── lab15_sec1/ ... lab15_sec6/     # Lab 15 (etiquetado del profesor): misma forma, solo van a train
└── tracking/                       # DAT-02 (trayectorias), rutas.tracking en config.yaml
    └── seq_00015_Final/
        ├── gt/gt.txt               # frame,id,x,y,w,h,conf,clase,visibilidad (formato MOT)
        └── frames.txt              # frame,imagen: une el frame del gt.txt con su imagen (frame 1 = _00000)
```

### Qué hay en el código

| Qué | Dónde |
|---|---|
| Contrato `procesar(video, canales, perfil) -> Resultados` | `src/tracker/pipeline.py` |
| Canal (tubo) y su línea de conteo, en JSON | `src/tracker/canales.py`, `configs/canales_cuadro_completo.json` |
| Detector por cuadro (solo cambian los pesos) | `src/tracker/detector.py` |
| Seguimiento por canal: un tracker por tubo, ByteTrack o BoT-SORT | `src/tracker/seguimiento.py`, `configs/bytetrack.yaml`, `configs/botsort.yaml` |
| Conteo: línea simple (lista) e histéresis (semana 2) | `src/tracker/conteo.py` |
| Evaluación del seguimiento contra DAT-02 | `src/tracker/evaluar_seguimiento.py` |
| Exportar, leer y validar el formato común | `src/tracker/formato.py` |
| Interfaz (Angelo) | `src/tracker/gui/` |
| Línea base y variante (detector, tracker, conteo) | `configs/perfiles/base.yaml`, `variante.yaml` |
| Split y `data.yaml` | `configs/split.yaml`, `scripts/preparar_split.py` |
| Videos: conteo, seguimiento, secuencia | `scripts/video_conteo.py`, `scripts/video_seguimiento.py`, `scripts/secuencia_a_video.py` |
| Referencia de conteo desde DAT-02 | `scripts/conteo_referencia.py`, `configs/conteo_real.yaml` |

Línea base de detección (YOLO11 del Lab 15 en la validación nueva, 8 secuencias de DAT-01): mAP@50 **0,9436** ([tabla](docs/tablas/map50_yolo11_val.md)).

> Lo que sigue (diseño, partición, reproducción y resultados) describe el **Lab 15** y su partición antigua de 6 secuencias; sus cifras no valen para la Solemne 3.
> Los scripts `entorno.py`, `grilla.py`, `contar.py`, `criterio.py`, `analisis.py` y `visualizador.py` del Lab 15 se quitaron del repositorio (siguen en el historial de git, antes del commit «chore: quitar scripts y resultados del Lab 15»). Estas secciones se conservan solo como referencia de cómo se obtuvo el detector.

## Inicio rápido

Todos los comandos se ejecutan desde la raíz del repositorio. Los datos no se incluyen: ver la sección Datos.

```powershell
uv sync
uv run python src/entrenar.py --nombre prueba --epocas 1
uv run python src/evaluar.py --split val
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
- **Seguimiento: ByteTrack.** Asocia casi todas las cajas, incluidas las de baja confianza (el detector entrega desde 0,10), para reducir trayectorias fragmentadas. El umbral de asociación `match_thresh` se elige en validación (ver `docs/metodologia.md`). Usa solo movimiento y cajas. No hay etiquetas de seguimiento, por lo que se elige el método más simple y explicable.
  Fuentes: Zhang et al., [ByteTrack](https://arxiv.org/abs/2110.06864); [Ultralytics Track](https://docs.ultralytics.com/modes/track/) (soporta ByteTrack, parámetros `track_high_thresh`, `track_buffer`, `match_thresh`).
- **Conteo: cruce de línea virtual.** La cámara es fija y mira desde arriba; los salmones avanzan en vertical, de arriba hacia abajo. La línea es horizontal (cruza todo el ancho del cuadro, cubre ambas vías) y está al 50 % del alto, medida desde arriba; se eligió en validación entre 40, 50 y 60 %, junto con `match_thresh` (0,8). Cada ID se cuenta una sola vez: cuando el centro de su caja cruza la línea hacia abajo o, si hubo un salto de cuadros, cuando aparece por primera vez sobre la línea o bajo ella sin subir (ver `docs/metodologia.md`).
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
│   ├── comun.py           # rutas, semilla, dispositivo, data.yaml generado, lectura de cuadros
│   ├── entrenar.py        # entrena UNA configuración
│   ├── evaluar.py         # mAP@0.5, mAP@0.5:0.95, precisión, recall (val o test)
│   └── tracker/           # el Tracker (Solemne 3): pipeline, detector, seguimiento, conteo, formato, gui/
├── scripts/               # preparar_split, videos de conteo y seguimiento, referencia de conteo
├── weights/               # best.pt (elegido) + best.yaml (ficha: corrida, mAP val, sha256)
├── logs/                  # evaluacion_val_best.json y evaluacion_test_best.json
├── analysis/              # análisis del Avance 1 del Lab 15 (conteo manual, referencia)
├── docs/                  # plan, formato común, metodología del Lab 15 y tablas
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

Metodología (métricas, criterio de éxito, plan de experimentos): ver `docs/metodologia.md`.

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
| 0. Probar el flujo (1 época, no es la entrega) | `uv run python src/entrenar.py --nombre prueba --epocas 1` | `logs/prueba/` (no toca `weights/`) |
| 1. Entrenar la configuración entregada (R2) | `uv run python src/entrenar.py --modelo yolo11n.pt --imgsz 640 --lr0 0.001 --nombre R2` | `logs/R2/` |
| 2. Detector en test (una vez) | `uv run python src/evaluar.py` | `logs/evaluacion_test_best.json` |

La grilla de 8 corridas (`grilla.py`), el criterio de éxito (`criterio.py`) y el conteo del Lab 15 (`contar.py`) se quitaron del repositorio; sus resultados quedaron en el informe del Lab 15. El conteo del Tracker se hace con `uv run tracker procesar`.

### Resultados presentados

Pesos `weights/best.pt` (corrida R2: yolo11n, 640, lr0 0.001; sha256 `c384a62e…a2f8`).

| Qué | Comando | Valor |
|---|---|---|
| mAP@0.5 en validación | `uv run python src/evaluar.py --split val` | 0,9431 |
| mAP@0.5 en test | `uv run python src/evaluar.py` | 0,9685 |

Los valores de test quedan en `logs/evaluacion_test_best.json`. La metodología del Lab 15 está en `docs/metodologia.md`.

### Notas de reproducibilidad

- Semilla 42, `deterministic=True`, optimizador SGD explícito (con `optimizer: auto` Ultralytics ignora `lr0`).
- `evaluar.py` usa el `imgsz` guardado en los pesos y umbrales fijos (`conf 0.001`, `iou 0.7`, lote 16).
- `plots=False`: Ultralytics no guarda imágenes del dataset en `logs/`. Los datos no salen de `data/`.
- Entrega: `git archive --format=zip --prefix=Contreras-Carrera/ -o Contreras-Carrera.zip HEAD` (incluye solo lo versionado: sin `data/`, `.venv/` ni `outputs/`).
