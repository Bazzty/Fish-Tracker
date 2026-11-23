# Línea base de detección: YOLO11 (Lab 15) en la validación nueva

> La línea base (YOLO11, `weights/best.pt`, perfil `base`) ya no está en `main`. Para reproducir lo que usa YOLO11 en este documento, usar la rama [`comparacion-yolo11-base`](https://github.com/Bazzty/Fish-Tracker/tree/comparacion-yolo11-base).

Pesos `weights/best.pt` (YOLO11n, imgsz 640, sha256 `c384a62e…a2f8`), sin reentrenar.
Validación: 8 secuencias de DAT-01 (`configs/split.yaml`), que el modelo nunca vio (se entrenó solo con las secuencias del Lab 15).

| Detector | Validación | mAP@50 | mAP@50-95 | Precisión | Recall |
|---|---|---|---|---|---|
| YOLO11n (Lab 15) | DAT-01, 8 secuencias | **0,9436** | 0,6274 | 0,9299 | 0,8904 |

Comando: `uv run python src/entrenamiento/evaluar.py --split val` → `resultados/evaluacion_val_best.json`.

El 0,9431 del README del Lab 15 se midió con otra partición (`seq_0002` del Lab 15) y no es comparable. Esta fila es la referencia para YOLO26 en la semana 2.
