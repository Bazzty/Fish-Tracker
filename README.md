# Fish-Counter

Sistema que detecta, sigue y cuenta salmones en video.
USS-ICIFH001 · Inteligencia Artificial · Lab 15 (base) y Solemne 3 (Tracker, cliente Duotek).

## Tracker (Solemne 3)

Aplicación de escritorio que abre un video, deja marcar los tubos (canales) y cuenta los salmones de cada uno sin contar dos veces el mismo pez. Intercambia archivos con el Validador en un [formato común](docs/formato_comun.md). Plan, responsables y estado: [`docs/plan.md`](docs/plan.md).

```powershell
uv sync
uv run tracker                                                  # abre la aplicación (interfaz en construcción)
uv run python scripts/secuencia_a_video.py seq_00015            # arma un video de prueba desde data/
uv run tracker inferir --video outputs/videos/seq_00015.mp4 --salida outputs/inferencia/seq_00015
uv run tracker validar docs/ejemplo_formato                     # comprueba una carpeta contra el formato común
```

| Qué | Dónde |
|---|---|
| Contrato `procesar(video, canales, perfil) -> Resultados` | `src/tracker/pipeline.py` |
| Canal y zona de conteo (JSON) | `src/tracker/canales.py` |
| Detector por cuadro (solo cambian los pesos) | `src/tracker/detector.py` |
| Seguimiento por canal (Alonso, pendiente) | `src/tracker/seguimiento.py` |
| Conteo: línea simple e histéresis (Alonso, pendiente) | `src/tracker/conteo.py` |
| Interfaz (Angelo, pendiente) | `src/tracker/gui/` |
| Exportar, leer y validar el formato común | `src/tracker/formato.py` |
| Línea base y variante | `configs/perfiles/base.yaml`, `variante.yaml` |

Línea base de detección (YOLO11 del Lab 15 en la validación nueva, 8 secuencias de DAT-01): mAP@50 **0,9436** ([tabla](docs/tablas/map50_yolo11_val.md)).

> Lo que sigue (diseño, partición, reproducción y resultados) describe el **Lab 15** y su partición antigua de 6 secuencias; sus cifras no valen para la Solemne 3.

## Inicio rápido

Al descomprimir el zip queda la carpeta `Contreras-Carrera/`; todos los comandos se ejecutan desde ahí. Los datos no se incluyen: ver la sección Datos.

```powershell
cd Contreras-Carrera
uv sync
uv run python src/entrenar.py --nombre prueba --epocas 1
uv run python src/evaluar.py --split val
uv run python src/contar.py --video clip.mp4
```

Qué hace cada uno: instala el entorno, entrena 1 época de prueba (no toca `weights/`), evalúa los pesos entregados (mAP@0.5 de validación 0,9431) y cuenta los salmones de un video, que deja anotado en `outputs/clip/anotado.mp4`. El detalle y los resultados presentados están en la sección Reproducir.

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
│   ├── entorno.py         # verifica Python, PyTorch, GPU y datos
│   ├── entrenar.py        # entrena UNA configuración
│   ├── grilla.py          # 8 corridas + línea base + selección en validación -> weights/best.pt
│   ├── evaluar.py         # mAP@0.5, mAP@0.5:0.95, precisión, recall (val o test)
│   ├── contar.py          # detector -> ByteTrack -> línea virtual -> video anotado + eventos
│   ├── criterio.py        # error de conteo por secuencia y total, veredicto contra umbrales
│   ├── analisis.py        # estadísticas de datos del Avance 1
│   └── visualizador.py    # revisar cuadros y etiquetas a mano
├── weights/               # best.pt (elegido) + best.yaml (ficha: corrida, mAP val, sha256)
├── logs/                  # grilla.csv, efectos.csv, linea_base.csv, curvas.png, criterio_*.json, R1..R8/
├── docs/                  # metodología, tablas y figuras del análisis
└── outputs/               # videos anotados y eventos (no se versiona)
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
uv run python src/entorno.py
```

`uv sync` instala PyTorch con CUDA 12.8 en Windows y Linux (necesario para la serie RTX 50) y desde PyPI en macOS.
`entorno.py` debe mostrar la GPU con `sm_120 ... OK`, `lap: OK` y las 6 secuencias con imágenes y etiquetas.
Si `uv sync` actualiza `uv.lock`, subir ese archivo al repositorio.

## Reproducir

Todos los comandos se ejecutan desde la raíz del repositorio. Los parámetros están en `configs/config.yaml`.

| Paso | Comando | Resultado |
|---|---|---|
| 0. Probar el flujo (1 época, no es la entrega) | `uv run python src/entrenar.py --nombre prueba --epocas 1` | `logs/prueba/` (no toca `weights/`) |
| 1. Entrenar la configuración entregada (R2) | `uv run python src/entrenar.py --modelo yolo11n.pt --imgsz 640 --lr0 0.001 --nombre R2` | `logs/R2/` |
| 2. Grilla: línea base + 8 corridas + selección | `uv run python src/grilla.py` | `logs/grilla.csv`, `logs/efectos.csv`, `logs/linea_base.csv`, `logs/curvas.png`, `weights/best.pt` |
| 3. Elegir línea y `match_thresh` en validación | `uv run python src/criterio.py --split val` | `logs/criterio_val.json`; fijar los valores en `config.yaml` |
| 4. Congelar (solo en el repositorio de trabajo, no en el zip) | `git add weights logs configs` · `git commit -m "feat: congela configuración del avance 2"` · `git tag avance2-final` | `weights/best.yaml` guarda el sha256 de los pesos |
| 5. Detector en test (una vez) | `uv run python src/evaluar.py` | `logs/evaluacion_test_best.json` |
| 6. Criterio de éxito en test (una vez) | `uv run python src/criterio.py --videos` | `logs/criterio_test.json`, `outputs/seq_000X/anotado.mp4` |
| 7. Contar en un video nuevo | `uv run python src/contar.py --video clip.mp4` | `outputs/clip/anotado.mp4`, `eventos.csv`, `cruces.csv`, `resumen.json` |

La grilla se puede interrumpir y relanzar: salta las corridas ya registradas. Para repartirla: `--solo R1 R2 R5 R6`.

### Resultados presentados

Pesos `weights/best.pt` (corrida R2: yolo11n, 640, lr0 0.001; sha256 `c384a62e…a2f8`), línea 0,50 y `match_thresh` 0,8.

| Qué | Comando | Valor |
|---|---|---|
| mAP@0.5 en validación | `uv run python src/evaluar.py --split val` | 0,9431 |
| mAP@0.5 en test | `uv run python src/evaluar.py` | 0,9685 |
| Criterio de éxito | `uv run python src/criterio.py` | mAP@0.5 val 0,9431 (cumple ≥ 0,90); conteo test 22 de 25, error 12 % (no cumple ≤ 10 %) |

Los mismos valores quedan en `logs/evaluacion_test_best.json` y `logs/criterio_test.json`. La metodología y la regla de conteo están en `docs/metodologia.md`.

Diagnóstico para el análisis de casos (cajas etiquetadas en vez del detector; separa errores del detector de los del seguimiento):

```powershell
uv run python src/criterio.py --split val --oraculo
uv run python src/contar.py --seq seq_0003 --oraculo
```

### Notas de reproducibilidad

- Semilla 42, `deterministic=True`, optimizador SGD explícito (con `optimizer: auto` Ultralytics ignora `lr0`).
- `evaluar.py` usa el `imgsz` guardado en los pesos y umbrales fijos (`conf 0.001`, `iou 0.7`, lote 16).
- `plots=False`: Ultralytics no guarda imágenes del dataset en `logs/`. Los datos no salen de `data/`.
- Entrega: `git archive --format=zip --prefix=Contreras-Carrera/ -o Contreras-Carrera.zip HEAD` (incluye solo lo versionado: sin `data/`, `.venv/` ni `outputs/`).
