# Fish-Tracker

Sistema que detecta, sigue y cuenta salmones en video.
USS-ICIFH001 · Inteligencia Artificial · Lab 15 (base) y Solemne 3 (Tracker, cliente Duotek).

Aplicación de escritorio que, a partir de un video, permite marcar los tubos (canales) y contar los salmones que pasan por cada uno sin contar dos veces el mismo pez. Los resultados se intercambian con el Validador mediante un [formato común](docs/formato_comun.md).

**Contenido:** [Inicio rápido](#inicio-rápido) · [Estructura](#estructura-del-repositorio) · [Interfaz](#interfaz) · [Tracker](#tracker) · [Entrenamiento](#entrenamiento-del-detector) · [Scripts](#scripts) · [Resultados](#resultados) · [Métricas y archivos de salida](#métricas-y-archivos-de-salida) · [Reproducibilidad](#reproducibilidad)

Documentos aparte:

- [`docs/formato_comun.md`](docs/formato_comun.md): contrato de archivos con el Validador (ejemplo en `docs/ejemplo_formato/`).
- [`docs/plan.md`](docs/plan.md): tareas, responsables y estado.
- [`docs/caso_dificil.md`](docs/caso_dificil.md): el caso de seq_00015 que explica el error de la línea base.

## Inicio rápido

Requisitos: [uv](https://docs.astral.sh/uv/) y git. Para entrenar, además, una GPU NVIDIA con driver reciente (`nvidia-smi` debe mostrar CUDA 12.8 o más). `uv sync` instala PyTorch con CUDA 12.8 en Windows y Linux (necesario para la serie RTX 50) y desde PyPI en macOS. Clonar en una ruta corta, sin espacios ni OneDrive. Si `uv sync` actualiza `uv.lock`, subir ese archivo.

Todos los comandos se ejecutan desde la raíz del repositorio. FFmpeg viene como dependencia (`imageio-ffmpeg`), así que los videos salen en H.264 sin pasos adicionales.

```bash
uv sync           # instala el entorno
uv run tracker    # abre la interfaz
```

Los datos no se versionan; los comandos marcados con 📂 los necesitan en `data/` (ver [Datos](#datos)).

## Estructura del repositorio

El código tiene tres partes: el **entrenamiento** del detector, el **tracker** (detectar, seguir y contar) y la **interfaz**, que es una capa sobre el tracker.

```
Fish-Tracker/
├── README.md                 este documento
├── pyproject.toml, uv.lock   dependencias; `uv run tracker` apunta a src/tracker/cli.py
│
├── src/
│   ├── comun.py              compartido: config, rutas, semilla, dispositivo, data.yaml, video H.264
│   │
│   ├── entrenamiento/        ENTRENAMIENTO del detector
│   │   ├── entrenar.py         entrena un YOLO con config.yaml
│   │   ├── experimentos.py     grilla corta YOLO26 (n/s × 2 versiones de datos)
│   │   └── evaluar.py          mAP@50, precisión y recall en val o test
│   │
│   └── tracker/              TRACKER: la aplicación
│       ├── cli.py              comandos de `uv run tracker`
│       ├── pipeline.py         contrato procesar(video, canales, perfil) -> Resultados
│       ├── canales.py          tubos y sus líneas (JSON de canales)
│       ├── detector.py         detector por cuadro
│       ├── seguimiento.py      un tracker por tubo
│       ├── conteo.py           línea simple y dos líneas
│       ├── salidas.py          carpetas de salida, seguimiento.json y conteo.json
│       ├── formato.py          formato común: exportar, leer y validar
│       ├── video.py            video anotado
│       ├── evaluar_seguimiento.py  IDF1, cambios de ID y conteo contra DAT-02
│       ├── comparar.py         tabla de error de conteo entre configuraciones
│       │
│       └── gui/              INTERFAZ
│           ├── app.py          ventana principal
│           ├── canvas.py       dibujo y edición de tubos sobre el video
│           ├── lineas.py       líneas A/B por defecto
│           ├── proceso.py      procesamiento en un hilo, perfil de la interfaz
│           ├── resultados.py   pantalla de resultados
│           └── diagnostico.py  diagnóstico del seguimiento
│
├── scripts/                  utilidades de línea de comandos (ver Scripts)
├── configs/
│   ├── config.yaml             parámetros de entrenamiento, evaluación y conteo
│   ├── split.yaml              partición train / val / test por secuencia
│   ├── perfiles/               base.yaml y variante.yaml
│   ├── <tracker>.yaml          bytetrack, botsort, botsort_reid, ocsort, deepsort
│   ├── tracker_variante.yaml   el tracker elegido para la variante
│   ├── canales_*.json          tubos de ejemplo
│   └── conteo_real.yaml        conteo de referencia por secuencia
├── weights/                  best.pt (YOLO11, base) y yolo26.pt (variante), cada uno con su ficha .yaml
├── resultados/               métricas (.json), curvas de entrenamiento (results.csv) y tablas/
├── docs/                     formato común, plan y caso difícil
├── data/                     datos privados (no se versiona)
└── outputs/                  videos y corridas (no se versiona)
```

## Interfaz

`uv run tracker` abre la aplicación (`src/tracker/gui/`). Procesa siempre con el perfil `variante`; la constante `PERFIL` de `src/tracker/gui/proceso.py` elige otro.

1. **Abrir video…** y recorrerlo con **▶ Reproducir** (Espacio) o arrastrando la barra.
2. **Dibujar tubo:** arrastrar el mouse sobre el video (Esc cancela). El tubo queda en edición: los cuadritos blancos cambian el tamaño, arrastrar por dentro lo mueve y los círculos amarillos mueven las líneas **A** y **B** (los peces avanzan de arriba hacia abajo). Un clic sobre un tubo lo vuelve a abrir; el panel derecho permite ajustar nombre, líneas (%) y posición, y **✔ Listo** lo fija.
3. Marcar ✔ en la lista los tubos que se analizan. **Guardar canales…** escribe el [JSON de tubos](#tubos-y-líneas-de-conteo) (`<video>.canales.json`) y **Cargar canales…** lo lee; un `canales.json` del Validador se procesa tal cual, con sus propias líneas.
4. **⚙ Procesar video:** corre el pipeline en un hilo aparte, con el video, las cajas e IDs, una barra de progreso y el conteo por tubo en vivo (un tubo sin peces muestra 0). **✖ Cancelar** lo detiene.
5. **Exportar resultados…** escribe el formato común en `<carpeta elegida>/<video>_<perfil>/` y lo valida. Los errores (sin video, sin tubos marcados, pesos no encontrados, carpeta sin permiso, archivos que no cumplen el formato) se muestran con un mensaje claro.
6. **Ver resultados:** el último procesamiento, o una carpeta del formato común (por ejemplo `docs/ejemplo_formato`). Muestra el conteo por tubo, los eventos de conteo y un **diagnóstico del seguimiento** (`diagnostico.py`) que clasifica *caja intermitente*, *ID perdido* e *ID nuevo* a partir de `trayectorias.csv`. Es una heurística sin etiquetas de referencia; sus umbrales están en `diagnostico.Params`.

Los tubos nuevos parten con las líneas en A = 55 % y B = 65 % del alto (`src/tracker/gui/lineas.py`).

## Tracker

### Comandos

| Comando | Qué hace |
|---|---|
| `uv run tracker` | Abre la interfaz. |
| `uv run tracker inferir` | Solo el detector sobre todo el video. No sigue ni cuenta. |
| `uv run tracker procesar` | Detector, seguimiento y conteo por tubo. Guarda los 5 archivos del formato común. |
| `uv run tracker validar` | Comprueba que una carpeta de resultados cumpla el formato común. |
| `uv run tracker evaluar-seguimiento` 📂 | IDF1, cambios de ID, MOTA y error de conteo contra las trayectorias de DAT-02. |
| `uv run tracker comparar` | Tabla de error de conteo entre configuraciones a partir de sus `metricas_*.json`. |

Si el video o el JSON no existen, el comando termina con `[ERROR] ...` y no deja archivos a medias.

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

### Contar los salmones de un video

Como el repositorio no incluye los videos originales, primero se arma uno a partir de las imágenes de `data/`. Luego, `procesar` ejecuta el detector, el seguimiento por tubo y el conteo, genera el video anotado e imprime la ubicación de cada archivo.

```bash
uv run python scripts/secuencia_a_video.py seq_00015                          # 📂
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos

uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos --perfil base            # línea base
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos --tracker configs/botsort.yaml
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales dos_tubos --conteo linea_simple
uv run tracker inferir --video outputs/videos/seq_00015.mp4                   # solo el detector -> outputs/deteccion/yolo26/seq_00015/
uv run tracker validar outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas     # comprueba el formato común
```

| Opción | Descripción |
|---|---|
| `--canales` | [JSON de tubos](#tubos-y-líneas-de-conteo), por ruta o por nombre de un archivo de `configs/`. |
| `--seq` | Nombre de la secuencia. Por defecto se toma del nombre del video. Si la secuencia tiene trayectorias en DAT-02, `conteo.json` incluye el conteo real y el error por tubo. |
| `--perfil`, `--tracker`, `--conteo` | Ver [Perfiles](#perfiles). |
| `--sin-video` | Omite el video anotado. |
| `--fps` | Cuadros por segundo del video anotado. Por defecto, los del video de entrada. Solo cambia la velocidad de reproducción, no el conteo. |
| `--salida` | Guarda todos los archivos en una sola carpeta. |

`secuencia_a_video.py` usa por defecto 10 cuadros por segundo (`conteo.fps_cuadros` de `configs/config.yaml`), que es la frecuencia de captura de las secuencias, y acepta `--fps` para cambiarla. Esos fps pasan a ser los del video de entrada y determinan `tiempo_s` en `seguimiento.json` y `conteo.json`, pero no el número de peces contados. Los saltos de numeración de la secuencia no se conservan.

Archivos generados con el perfil por defecto:

```
outputs/seguimiento/yolo26_ocsort/seq_00015/seguimiento.json      trayectoria de cada pez, por tubo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/conteo.json     conteo del sistema, conteo real y error por tubo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/anotado.mp4     video con tubos, líneas, IDs y conteo
outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas/                además, los 5 archivos del formato común
```

Las rutas siguen el esquema `outputs/<operación>/<detector>_<tracker>/<secuencia>/`. En el video, la línea A es amarilla, la línea B es naranja y cada pez cambia a verde cuando se cuenta. Para regenerarlo: `uv run python scripts/video_conteo.py <carpeta del conteo> --video <video>`, con `--fps` opcional.

### Tubos y líneas de conteo

`procesar` cuenta los peces por tubo. Los tubos y sus líneas se definen en un archivo JSON que se indica con `--canales`, por **ruta** o por **nombre** de un archivo de `configs/` (`configs/canales_mis_tubos.json` se usa como `--canales mis_tubos`). El archivo puede generarse desde la interfaz o escribirse a mano.

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

| Campo | Descripción |
|---|---|
| `version` | Versión del formato. Siempre `1`. |
| `video` | Nombre y tamaño del video en píxeles. Es informativo. |
| `id` | Identificador único del tubo (`canal_1`, `canal_2`, …). Es la clave del tubo en todos los resultados. |
| `caja` | Rectángulo del tubo en píxeles: `[x1, y1, x2, y2]`, esquina superior izquierda e inferior derecha, con `x1 < x2` e `y1 < y2`. |
| `nombre` | Etiqueta que se muestra en el video y en la interfaz. |
| `linea_a` | Posición de la línea A como **fracción del alto del tubo**, desde arriba (0 = borde superior, 1 = borde inferior). Con línea simple es la única línea; con dos líneas, es donde el pez queda armado. |
| `linea_b` | Posición de la línea B, en la misma escala. Solo la usa la regla de dos líneas: es donde el pez se cuenta. Debe cumplirse `0 ≤ linea_a < linea_b ≤ 1`. |
| `activo` | `false` indica que el tubo está marcado, pero no se analiza. |
| `forma` | Forma del tubo. Por ahora, siempre `"rect"`. |

La coordenada de cada línea en píxeles es `y = y1 + fracción × (y2 − y1)`. Cada pez se asigna al tubo que contiene **el centro** de su caja; los que quedan fuera de todos los tubos, por ejemplo sobre la pared que los separa, no se cuentan.

| Nombre para `--canales` | Archivo | Tubos (video de 1456 × 1088) |
|---|---|---|
| `cuadro_completo` | `configs/canales_cuadro_completo.json` | Un tubo del tamaño del cuadro, con líneas en 0,5 y 0,6. |
| `dos_tubos` | `configs/canales_dos_tubos.json` | Mitad izquierda y mitad derecha, con líneas en 0,5 y 0,6. |

Al ubicar las líneas:

- Cada tubo puede tener sus propias líneas. El conteo real se calcula con la línea A del mismo archivo, así que mover la A cambia también la referencia; mover solo la B, no.
- Conviene no separarlas demasiado: el tracker debe seguir al pez entre ambas. A 10 cuadros por segundo un pez baja hasta unos 100 píxeles por cuadro; con líneas en 0,5 y 0,6 la separación es de unos 109 píxeles, y con 0,4 y 0,6, de unos 210. Si en el video anotado hay peces que cruzan A pero no se cuentan, conviene acercarlas (por ejemplo, a 0,45 y 0,55).
- El nombre del video debe coincidir con el de la secuencia (`seq_00015.mp4`); si no, hay que indicar `--seq` para tener el conteo real.
- Las cajas deben cubrir toda la zona por donde pasan los peces, y el espacio entre tubos debe ser solo la pared.
- `evaluar-seguimiento` y el barrido no leen este archivo: usan un tubo del tamaño del cuadro, con la línea A en `conteo.linea` de `configs/config.yaml` (0,50) y la B 0,1 más abajo.

### Evaluar el seguimiento contra DAT-02 📂

`evaluar-seguimiento` ejecuta el detector una vez por secuencia y aplica cada tracker sobre las mismas detecciones. Con `--oraculo`, las detecciones se reemplazan por las cajas etiquetadas, lo que permite distinguir los errores del tracker de los del detector.

```bash
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml
uv run tracker evaluar-seguimiento --conjunto val --trackers configs/bytetrack.yaml configs/botsort.yaml configs/botsort_reid.yaml configs/ocsort.yaml configs/deepsort.yaml --oraculo
uv run python scripts/video_seguimiento.py seq_00015 --tracker ocsort
```

Val se usa para comparar y ajustar. La medición final, con el tracker de la variante, se hace una sola vez en test ([resultado](resultados/tablas/seguimiento_test.md)):

```bash
uv run tracker evaluar-seguimiento --conjunto test
uv run tracker evaluar-seguimiento --conjunto test --perfil base     # línea base, para comparar
```

Los resultados se guardan en `outputs/evaluacion_seguimiento/<detector>/` (`yolo26`, `best` u `oraculo`): las trayectorias de cada tracker en `<secuencia>/<tracker>.txt` (formato MOT; `video_seguimiento.py` deja a su lado `<tracker>.mp4`) y las métricas en `metricas_<grupo>_<regla>.csv` y `.json` ([qué significa cada columna](#evaluación-del-seguimiento)).

| Tracker | Archivo | Biblioteca | Observaciones |
|---|---|---|---|
| ByteTrack | `configs/bytetrack.yaml` | Ultralytics | Tracker del perfil `base`. |
| BoT-SORT | `configs/botsort.yaml` | Ultralytics | |
| BoT-SORT con ReID | `configs/botsort_reid.yaml` | Ultralytics | Compara la apariencia de cada pez con los pesos del detector; requiere la imagen y es más lento. |
| OC-SORT | `configs/ocsort.yaml` | `trackers` | Requiere Python 3.11 o superior. |
| DeepSORT | `configs/deepsort.yaml` | `deep-sort-realtime` | Compara la apariencia con una red MobileNet; requiere la imagen y es más lento. |

### Elegir el tracker de la variante 📂

`scripts/barrido_tracker.py` evalúa 28 combinaciones de parámetros de los cinco trackers, con el detector y con el oráculo, y las ordena por error de conteo, luego por IDF1 y luego por cambios de ID. Escribe la tabla y la decisión en [`resultados/tablas/comparacion_trackers.md`](resultados/tablas/comparacion_trackers.md). Con `--aplicar`, el ganador se copia a `configs/tracker_variante.yaml`; `--rapido` omite DeepSORT y BoT-SORT con ReID, que son los más lentos.

Por defecto usa las secuencias de val; `--yaml test` usa las de test y escribe `comparacion_trackers_test.md`, sin reemplazar la tabla de val. El ganador se elige solo en val: con test, `--aplicar` no está permitido, ya que test sirve para confirmar la decisión.

```bash
uv run python scripts/barrido_tracker.py --aplicar
uv run python scripts/barrido_tracker.py --yaml test
```

### Comparar la base con la variante

`tracker comparar` arma una tabla de error de conteo a partir de los `metricas_*.json` de `evaluar-seguimiento`; cada entrada es `ETIQUETA=RUTA.json`, o `ETIQUETA=RUTA.json:TRACKER` si el JSON trae varios trackers. Así se armó [`error_conteo_test.md`](resultados/tablas/error_conteo_test.md):

```bash
uv run tracker comparar "Base=resultados/seguimiento_test_base.json" "Variante=resultados/seguimiento_test_variante.json" --salida tabla.md
```

### Conteo de referencia 📂

`scripts/conteo_referencia.py --guardar` escribe en `configs/conteo_real.yaml` el conteo de cada secuencia de val y test según DAT-02, con un tubo del tamaño del cuadro y la línea A en `conteo.linea` de `configs/config.yaml`. Reemplaza el conteo manual del Lab 15.

```bash
uv run python scripts/conteo_referencia.py
uv run python scripts/conteo_referencia.py --guardar
```

## Entrenamiento del detector

### Datos

Los datos no se versionan. Deben ubicarse en `data/` con esta estructura:

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

En DAT-02 las secuencias se llaman `seq_000XX`; los nombres `seq_000X` corresponden al Lab 15.

### Preparar la partición 📂

`scripts/preparar_split.py` lee `configs/split.yaml`, única fuente de la partición (el criterio de selección está documentado en ese archivo), y genera dos archivos de datos con la misma validación y la misma prueba:

- `runs/data_dat01.yaml`: entrenamiento solo con DAT-01.
- `runs/data_lab15_dat01.yaml`: entrenamiento con Lab 15 y DAT-01.

También genera la tabla [`resultados/tablas/cuadros_por_split.md`](resultados/tablas/cuadros_por_split.md). Con los mismos datos, el resultado es siempre el mismo.

```bash
uv run python scripts/preparar_split.py
```

### Entrenar y medir 📂

```bash
# Medir el detector (mAP@50, precisión, recall)
uv run python src/entrenamiento/evaluar.py --split val                      # guarda resultados/evaluacion_val_best.json
uv run python src/entrenamiento/evaluar.py --pesos weights/yolo26.pt --split val
uv run python src/entrenamiento/evaluar.py                                  # test: usar una sola vez, al final

# Probar el entrenamiento con 1 época; no toca weights/
uv run python src/entrenamiento/entrenar.py --nombre prueba --epocas 1

# Experimentos cortos YOLO26 (4 corridas, ~3 h): escribe resultados/tablas/experimentos_yolo26.md
uv run python src/entrenamiento/experimentos.py

# Entrenamiento final del ganador (100 épocas, paciencia 20)
uv run python src/entrenamiento/entrenar.py --modelo yolo26n.pt --datos dat01 --imgsz 640 --lr0 0.001 --nombre yolo26_final
```

## Scripts

| Script | Parte | Qué hace |
|---|---|---|
| `preparar_split.py` 📂 | Entrenamiento | Escribe los dos `data.yaml` de entrenamiento y la tabla de cuadros por conjunto. |
| `secuencia_a_video.py` 📂 | Tracker | Arma un `.mp4` H.264 desde las imágenes de una secuencia, porque no hay videos originales. `--fps` fija la velocidad (por defecto 10). |
| `video_conteo.py` | Tracker | Rehace el `anotado.mp4` de una corrida de `procesar` (útil con `--sin-video`). `--fps` cambia la velocidad. |
| `video_seguimiento.py` 📂 | Tracker | Dibuja caja, ID y ruta de cada pez a partir de `evaluar-seguimiento`. `--fps` cambia la velocidad. |
| `barrido_tracker.py` 📂 | Tracker | Prueba umbrales de los 5 trackers contra DAT-02 y deja la tabla y la decisión; `--aplicar` fija el ganador en el perfil `variante`. |
| `conteo_referencia.py` 📂 | Tracker | Aplica la regla de conteo a las trayectorias etiquetadas (el conteo correcto) y lo compara con el del tracker. |
| `generar_ejemplo_formato.py` | Interfaz | Regenera `docs/ejemplo_formato/` con datos sintéticos. **Sobrescribe esos archivos.** |

## Resultados

Todas las cifras son de secuencias que el modelo no vio al entrenar. Val sirvió para elegir y test se usó una sola vez, al final.

| Qué | Línea base (YOLO11 + ByteTrack) | Variante (YOLO26 + OC-SORT + dos líneas) | Detalle |
|---|---|---|---|
| Detector, mAP@50 en val | 0,9436 | 0,9916 | [yolo11_vs_yolo26.md](resultados/tablas/yolo11_vs_yolo26.md) |
| Detector, recall en val | 0,8904 | 0,9673 | [yolo11_vs_yolo26.md](resultados/tablas/yolo11_vs_yolo26.md) |
| Detector, mAP@50 en test | — | 0,9913 | [yolo11_vs_yolo26.md](resultados/tablas/yolo11_vs_yolo26.md) |
| Conteo en val (8 secuencias) | — | 135 de 137 peces, IDF1 93,0 % | [comparacion_trackers.md](resultados/tablas/comparacion_trackers.md) |
| **Conteo en test (9 secuencias)** | **96 de 132 peces (error 27,3 %), IDF1 52,0 %** | **131 de 132 peces (error 0,8 %), IDF1 93,2 %** | [error_conteo_test.md](resultados/tablas/error_conteo_test.md), [seguimiento_test.md](resultados/tablas/seguimiento_test.md) |

Cómo se eligió cada pieza:

- **Detector:** YOLO26n con DAT-01 ([experimentos_yolo26.md](resultados/tablas/experimentos_yolo26.md)). Se compararon n y s y dos versiones de datos; quedaron empatados y ganó el n por ser más liviano y rápido. También se comprobó yolo26s a 100 épocas y lr0 0,01 en lugar de 0,001, sin mejora.
- **Tracker:** OC-SORT, elegido en val entre cinco trackers y 28 combinaciones de parámetros ([comparacion_trackers.md](resultados/tablas/comparacion_trackers.md)) y confirmado en test ([comparacion_trackers_test.md](resultados/tablas/comparacion_trackers_test.md)).
- **Base vs. variante:** cambiando un componente a la vez, el que más reduce el error es el tracker. La base pierde peces cuando el detector falla justo sobre la línea, como en el [caso difícil](docs/caso_dificil.md) ([error_conteo_test.md](resultados/tablas/error_conteo_test.md)).

Límite: train, val y test vienen de la misma cámara. Las cifras valen para este montaje; en otra instalación hay que validar de nuevo.

## Métricas y archivos de salida

### Evaluación del seguimiento

`evaluar-seguimiento` compara cada tracker con las trayectorias etiquetadas de DAT-02. Una caja del tracker es el mismo pez que una caja etiquetada cuando se superponen al menos un 50 % (IoU ≥ 0,5). `<grupo>` es el conjunto (`val`, `test`) o las secuencias de `--seq`; `<regla>`, `linea_simple` o `dos_lineas`; `<detector>`, el nombre de los pesos (`yolo26`, `best`) u `oraculo`. Con `--oraculo`, los errores que persisten son del tracker y no del detector.

| Columna del CSV | Clave en el JSON | Significado | Deseable |
|---|---|---|---|
| TRACKER | — | Tracker evaluado (nombre de su archivo YAML). | — |
| SEQUENCE | — | Secuencia evaluada. La fila `TOTAL` agrega todas. | — |
| PERCENTAGE OF CORRECT IDs | `IDF1` | Porcentaje del tiempo en que el tracker mantiene **el mismo ID** para cada pez. Es la métrica más relacionada con no contar dos veces un pez. | Alto |
| TIMES ID CHANGED | `IDSW` | Veces que un pez **cambia de ID**, porque el tracker lo pierde y le da uno nuevo o porque intercambia el ID con otro pez. | Bajo |
| OVERALL TRACKING ACCURACY (MOTA) | `MOTA` | Exactitud global: descuenta peces no encontrados, cajas sobrantes y cambios de ID respecto del total de cajas etiquetadas. Puede ser negativa. | Alto |
| — (solo en el JSON) | `MOTP` | Superposición promedio de las cajas bien asociadas con la etiquetada. | Alto |
| EXTRA BOXES | `FP` | Cajas del tracker que **no corresponden a ningún pez** etiquetado. | Bajo |
| MISSING BOXES | `FN` | Cajas de peces etiquetados que el tracker **no encontró**. Un valor alto suele indicar fallas del detector. | Bajo |
| Frag | `Frag` | Veces que el seguimiento de un pez **se interrumpe y se retoma**, aunque conserve el ID. | Bajo |
| MT | `MT` | Peces **seguidos la mayor parte del tiempo** (al menos 80 % de los cuadros en que aparecen). | Alto |
| ML | `ML` | Peces **seguidos muy poco tiempo** (menos del 20 % de los cuadros en que aparecen). | Bajo |
| TOTAL FISHES | `peces_gt` | Peces distintos según el etiquetado. | — |
| FISHES COUNTED BY TRACKER | `ids_tracker` | IDs distintos que creó el tracker. Si supera a TOTAL FISHES, el tracker dio IDs nuevos a peces que ya seguía. | Cercano a TOTAL FISHES |
| COUNT TRACKER | `conteo_tracker` | Peces **contados por el sistema** con la regla del perfil. | Cercano a COUNT REFERENCE |
| COUNT REFERENCE | `conteo_referencia` | **Conteo real**: la línea simple aplicada a las trayectorias etiquetadas. | — |
| COUNT ERROR | `error_conteo` | \|COUNT TRACKER − COUNT REFERENCE\|. Es la comparación principal del plan. En la fila `TOTAL`, se calcula sobre las sumas. | 0 |

### `seguimiento.json` y `conteo.json`

Ambos traen `corrida` (fecha, secuencia, video, perfil; `modelo` con pesos, confianza mínima e IoU del NMS; `seguimiento` con el tracker y sus parámetros; `fps`, `ancho`, `alto` y `cuadros`) y `canales[]` (cada tubo con `id`, `nombre`, `caja`, `activo` y sus líneas, como fracción y en píxeles).

| Archivo | Campo | Significado |
|---|---|---|
| `seguimiento.json` | `resumen.<canal>.peces_seguidos` | Peces (IDs) seguidos en el tubo. |
| | `peces_por_canal.<canal>[]` | Cada pez: `id`, `primer_cuadro`, `ultimo_cuadro`, `cuadros_vistos` y `trayectoria`. |
| | `trayectoria[]` | Cada cuadro en que se vio: `cuadro` (desde 0), `imagen`, `tiempo_s`, `caja` (`x1`, `y1`, `x2`, `y2`, `ancho`, `alto`), `centro` (`x`, `y`) y `confianza`. |
| `conteo.json` | `regla_de_conteo` | Regla usada y sus parámetros (mínimo de cuadros y herencia de estado). |
| | `conteo_real` | Origen del conteo real (DAT-02) o el motivo por el que no está disponible. |
| | `resultado.por_canal.<canal>` | `contados_por_el_sistema`, `conteo_real` y `error`. |
| | `resultado.total` | Lo mismo, sumando todos los tubos. |
| | `eventos[]` | Cada pez contado: `canal`, `id`, `cuadro`, `imagen`, `tiempo_s` y `conteo` (acumulado del tubo). |

Los 5 archivos del formato común (`meta.json`, `canales.json`, `detecciones.csv`, `trayectorias.csv`, `conteos.csv`) están descritos en [`docs/formato_comun.md`](docs/formato_comun.md).

## Reproducibilidad

- Semilla 42, `deterministic=True` y optimizador SGD explícito (con `optimizer: auto` Ultralytics ignora `lr0`).
- `evaluar.py` usa el `imgsz` guardado en los pesos y umbrales fijos (`conf 0.001`, `iou 0.7`, lote 16).
- `plots=False`: Ultralytics no guarda imágenes del dataset en `resultados/`. Los datos no salen de `data/`.
- Entrega: `git archive --format=zip --prefix=Fish-Tracker/ -o Fish-Tracker.zip HEAD` (incluye solo lo versionado: sin `data/`, `.venv/` ni `outputs/`).

Para trabajar con el equipo:

```bash
git fetch && git switch develop && git pull       # traer lo último de develop
git switch -c nombre-de-la-rama                   # rama nueva para un cambio
```
