# Plan Tracker: tareas, archivos y estado

Fuente: «Planificación Tracker – Contador de salmones» (9 nov 2026). Entrega final: 24 de noviembre.
Estados: **hecha** · **en curso** · **pendiente**. Todo lo nuevo vive en `src/tracker/`; el pipeline del Lab 15 en `src/` no se toca.

## Semana 1 (10–16 nov)

| Responsable | Tarea | Archivos | Estado |
|---|---|---|---|
| Bastian | Estructura del repo y `uv run tracker` | `pyproject.toml`, `src/tracker/cli.py`, `src/tracker/gui/app.py` | hecha (abre una ventana vacía) |
| Bastian | Contrato `procesar(video, canales)` | `src/tracker/pipeline.py`, `src/tracker/canales.py`, `configs/perfiles/` | hecha |
| Bastian | Pesos YOLO11 y script de inferencia por cuadro | `src/tracker/detector.py`, `uv run tracker inferir`, `scripts/secuencia_a_video.py` | hecha (probado en `seq_00015`) |
| Bastian | Formato común con archivo de ejemplo | `docs/formato_comun.md`, `src/tracker/formato.py`, `docs/ejemplo_formato/` | en curso (falta que lo acepte un equipo del Validador) |
| Bastian | mAP@50 de YOLO11 en la validación nueva | `resultados/tablas/map50_yolo11_val.md`, `resultados/evaluacion_val_best.json` | hecha (0,9436) |
| Alonso | Secuencias de entrenamiento y split | `data/`, `configs/split.yaml`, `scripts/preparar_split.py` | hecha (`scripts/preparar_split.py`: dos `data.yaml` en `runs/` y [tabla](../resultados/tablas/cuadros_por_split.md): 69 / 16 / 15 % de cuadros y cajas) |
| Alonso | Revisión de consistencia entre etiquetados | `docs/` (informe) | pendiente |
| Alonso | Seguimiento por canal (ByteTrack) | `src/tracker/seguimiento.py` | hecha (un tracker por canal; ByteTrack, BoT-SORT (con o sin ReID), OC-SORT o DeepSORT según el perfil; video con `scripts/video_conteo.py`) |
| Alonso | Conteo por canal, línea simple | `src/tracker/conteo.py`, `scripts/video_conteo.py` | hecha (`uv run tracker procesar` de punta a punta, probado contra DAT-02) |
| Alonso | Referencia de conteo por canal de val y test, aplicando la regla de conteo a las trayectorias de DAT-02 | `scripts/conteo_referencia.py`, `configs/conteo_real.yaml` | en curso (script listo; falta `--guardar` con DAT-02) |
| Angelo | Interfaz: abrir video, dibujar tubos y zona, guardar JSON | `src/tracker/gui/` | pendiente (stub) |
| Angelo | Pantalla de resultados con datos de ejemplo | `src/tracker/gui/`, `docs/ejemplo_formato/` | pendiente |
| Angelo | Diagnóstico del seguimiento con YOLO11 | `docs/` (informe) | pendiente |

**Hito:** desde la interfaz se abre un video, se eligen 2 tubos y se obtiene el conteo base de cada uno.

## Semana 2 (17–23 nov)

| Responsable | Tarea | Archivos | Estado |
|---|---|---|---|
| Bastian | Entrenar YOLO26 (solo DAT-01 y Lab 15 + DAT-01) | `src/entrenamiento/entrenar.py`, `src/entrenamiento/experimentos.py`, `resultados/tablas/experimentos_yolo26.md`, `configs/split.yaml` | hecha (ganador: yolo26n con dat01) |
| Bastian | Elegir detector y dejar pesos en `weights/` | `weights/yolo26.pt`, `configs/perfiles/variante.yaml` | hecha |
| Bastian | Error de conteo base vs variante y caso difícil | `src/tracker/comparar.py`, `docs/caso_dificil.md` | hecha (test: base 96 / 132, variante 131 / 132; [tabla](../resultados/tablas/error_conteo_test.md)) |
| Bastian | Integración y entrega | todo | en curso (clon limpio de develop instala y abre en macOS; falta merge a main) |
| Alonso | Conteo con histéresis, filtro y herencia de estado | `src/tracker/conteo.py`, `configs/perfiles/variante.yaml` | hecha (perfil por defecto; en test cuenta 131 de 132 peces, [tabla](../resultados/tablas/seguimiento_test.md)) |
| Alonso | Ajuste de ByteTrack y comparación de trackers (IDF1, ID switches contra DAT-02) | `src/tracker/seguimiento.py`, `src/tracker/evaluar_seguimiento.py`, `configs/{bytetrack,botsort,botsort_reid,ocsort,deepsort}.yaml`, `scripts/barrido_tracker.py` | hecha (ganador OC-SORT en val, [tabla](../resultados/tablas/comparacion_trackers.md); en test IDF1 93,2 %) |
| Angelo | Avance en vivo y conteo por canal | `src/tracker/gui/` | pendiente |
| Angelo | Exportar al formato común, con errores claros | `src/tracker/formato.py`, `src/tracker/gui/` | pendiente |
| Angelo | Prueba con el Validador y README de uso | `README.md` | pendiente |

## Pendientes de decisión
- Aceptación del formato común por el Validador (`docs/formato_comun.md`).
- Los videos originales no están en el repo: para probar se arman desde `data/` con `scripts/secuencia_a_video.py`, y se pierden los saltos de numeración.
