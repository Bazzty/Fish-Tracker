# YOLO11 vs YOLO26

> La línea base (YOLO11, `weights/best.pt`, perfil `base`) ya no está en `main`. Para reproducir lo que usa YOLO11 en este documento, usar la rama [`comparacion-yolo11-base`](https://github.com/Bazzty/Fish-Tracker/tree/comparacion-yolo11-base).

Validación (split nuevo, 8 secuencias de DAT-01). Cifras de `resultados/evaluacion_val_*.json`.

| Detector | Split | mAP@50 | mAP@50:95 | Precisión | Recall |
|---|---|---|---|---|---|
| YOLO11n (`weights/best.pt`) | val | 0,9436 | 0,6274 | 0,9299 | 0,8904 |
| YOLO26n (`weights/yolo26.pt`) | val | 0,9916 | 0,7446 | 0,9721 | 0,9673 |

## Test (9 secuencias de DAT-01, evaluado una sola vez)

Solo el modelo elegido. Cifras de `resultados/evaluacion_test_yolo26.json`.

| Detector | Split | mAP@50 | mAP@50:95 | Precisión | Recall |
|---|---|---|---|---|---|
| YOLO26n (`weights/yolo26.pt`) | test | 0,9913 | 0,8009 | 0,9687 | 0,9700 |

YOLO11 no se evaluó en test con el split nuevo; `resultados/evaluacion_test_best.json` es del split antiguo del Lab 15 y no es comparable.
