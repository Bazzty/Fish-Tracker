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
| Bastian | mAP@50 de YOLO11 en la validación nueva | `docs/tablas/map50_yolo11_val.md`, `logs/evaluacion_val_best.json` | hecha (0,9436) |
| Alonso | Secuencias de entrenamiento y split | `data/`, `configs/split.yaml` | hecha |
| Alonso | Revisión de consistencia entre etiquetados | `docs/` (informe) | pendiente |
| Alonso | Seguimiento por canal (ByteTrack) | `src/tracker/seguimiento.py` | pendiente (stub con contrato) |
| Alonso | Conteo por canal, línea simple | `src/tracker/conteo.py` | pendiente (stub con contrato) |
| Alonso | Conteo manual por canal de val y test | `configs/conteo_real.yaml` | pendiente (hoy tiene las secuencias antiguas) |
| Angelo | Interfaz: abrir video, dibujar tubos y zona, guardar JSON | `src/tracker/gui/` | pendiente (stub) |
| Angelo | Pantalla de resultados con datos de ejemplo | `src/tracker/gui/`, `docs/ejemplo_formato/` | pendiente |
| Angelo | Diagnóstico del seguimiento con YOLO11 | `docs/` (informe) | pendiente |

**Hito:** desde la interfaz se abre un video, se eligen 2 tubos y se obtiene el conteo base de cada uno.

## Semana 2 (17–23 nov)

| Responsable | Tarea | Archivos | Estado |
|---|---|---|---|
| Bastian | Entrenar YOLO26 (solo DAT-01 y Lab 15 + DAT-01) | `src/entrenar.py`, `configs/split.yaml` | pendiente |
| Bastian | Elegir detector y dejar pesos en `weights/` | `weights/`, `configs/perfiles/variante.yaml` | pendiente |
| Bastian | Error de conteo base vs variante y caso difícil | `src/tracker/comparar.py` (por crear), `docs/` | pendiente |
| Bastian | Integración y entrega | todo | pendiente |
| Alonso | Conteo con histéresis, filtro y herencia de estado | `src/tracker/conteo.py` | pendiente |
| Alonso | Ajuste de ByteTrack y comparación de trackers (IDF1, ID switches contra DAT-02) | `src/tracker/seguimiento.py`, `configs/bytetrack.yaml` | pendiente |
| Angelo | Avance en vivo y conteo por canal | `src/tracker/gui/` | pendiente |
| Angelo | Exportar al formato común, con errores claros | `src/tracker/formato.py`, `src/tracker/gui/` | pendiente |
| Angelo | Prueba con el Validador y README de uso | `README.md` | pendiente |

## Pendientes de decisión
- Aceptación del formato común por el Validador (`docs/formato_comun.md`).
- Los videos originales no están en el repo: para probar se arman desde `data/` con `scripts/secuencia_a_video.py`, y se pierden los saltos de numeración.
- `src/grilla.py` copia el ganador a `weights/best.pt`: no ejecutarla sin cambiarle el destino.
- Material del Lab 15 que sigue describiendo la partición antigua: `analysis/`, `docs/tablas/*.csv`, `docs/figuras/`, `docs/metodologia.md` y `logs/` (R1..R8, `grilla.csv`, `criterio_*`).
