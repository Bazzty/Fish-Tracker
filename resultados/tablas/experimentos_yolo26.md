# Experimentos YOLO26 (val)

| modelo | datos | epocas_hechas | map50 | map50_95 | precision | recall |
|---|---|---|---|---|---|---|
| yolo11n (base) | lab15 (split antiguo) | - | 0.9436 | 0.6274 | 0.9299 | 0.8904 |
| yolo26n.pt | dat01 | 29 | 0.9910 | 0.7427 | 0.9769 | 0.9591 |
| yolo26n.pt | lab15_dat01 | 20 | 0.9918 | 0.7400 | 0.9792 | 0.9559 |
| yolo26s.pt | dat01 | 30 | 0.9923 | 0.7392 | 0.9751 | 0.9685 |
| yolo26s.pt | lab15_dat01 | 20 | 0.9916 | 0.7426 | 0.9685 | 0.9670 |

Protocolo común a todas las corridas (`configs/config.yaml`): imgsz 640, semilla 42 con `deterministic=True`, SGD con lr0 0,001, lote 16, 30 épocas como máximo con paciencia 10. El final y las comprobaciones de abajo usan 100 épocas con paciencia 20. `epocas_hechas` es la época en que paró cada corrida.

Regla: gana el mayor mAP@50 entre los YOLO26; si el modelo n queda a menos de 0.01 del mejor, gana el n.

Ganador según la regla automática del script: yolo26n.pt con lab15_dat01 (empate de mAP@50; ver «Por qué»).

## Por qué
- Las 4 corridas quedan entre 0,9910 y 0,9923 de mAP@50 (0,0013 de diferencia), todo dentro del empate de 0,01. Entre n y s no hay diferencia real, y entre A y B tampoco (n: 0,9910 contra 0,9918).
- Con el empate gana el modelo n, que es más rápido en inferencia, y eso importa para el video en vivo. Entre n con dat01 y n con lab15_dat01 desempata el recall (0,9591 contra 0,9559); a igualdad gana A (dat01), que usa menos datos y tiene menos riesgo de dominio. La regla automática del script elige lab15_dat01 por 0,0008 de mAP@50, que es un empate.
- Límite del método: yolo26s con dat01 llegó a 30 épocas sin parar por paciencia y tiene el mejor recall (0,9685), así que todavía mejoraba. Con 100 épocas podría alcanzar o superar al n. Las otras tres corridas pararon antes (29, 20 y 20 épocas), y 30 épocas pueden favorecer al n, que converge antes.
- Todos los YOLO26 superan por mucho al YOLO11 de referencia (0,9436), pero esa referencia usa el split antiguo. Conviene revisar con Alonso si hay fuga de datos entre train y val (secuencias consecutivas del mismo video).

Ganador final: yolo26n con dat01 (criterio: empate → n; desempate por recall; A ante empate)

## Comprobación: YOLO26s con 100 épocas
Como yolo26s_dat01 llegó a 30 épocas sin parar por paciencia, se entrenó con el mismo protocolo que el final (yolo26s.pt, dat01, 100 épocas, paciencia 20). Paró en la época 52.

| val | yolo26s (52 ép.) | yolo26n final (47 ép.) |
|---|---|---|
| mAP@50 | 0.9914 | 0.9916 |
| mAP@50:95 | 0.7448 | 0.7446 |
| precisión | 0.9803 | 0.9721 |
| recall | 0.9559 | 0.9673 |

Criterio: el s reemplaza al n solo si supera en +0,01 el mAP@50:95 o el recall sin bajar el mAP@50. No lo cumple: empata en mAP y pierde 0,011 de recall. **Se mantiene yolo26n**: pierde menos peces, pesa unos 5 MB contra unos 20 MB y es más rápido para el video en vivo.

## Comprobación: lr0 0,01 en lugar de 0,001
El lr0 0,001 se heredó de la línea base YOLO11 para que la comparación fuera justa y no se había probado otro valor. Se entrenó yolo26n con dat01 y lr0 0,01, con el mismo protocolo que el final (100 épocas, paciencia 20). Hizo 89 épocas (el final, 47).

| val | lr0 0,01 (89 ép.) | lr0 0,001 (47 ép., final) |
|---|---|---|
| mAP@50 | 0.9925 | 0.9916 |
| mAP@50:95 | 0.7447 | 0.7446 |
| precisión | 0.9758 | 0.9721 |
| recall | 0.9654 | 0.9673 |

Criterio: el cambio de lr0 se adopta solo si supera en +0,01 el mAP@50:95 o el recall sin bajar el mAP@50. No lo cumple: el mAP@50 queda dentro del empate (+0,0009), el mAP@50:95 es igual y el recall baja 0,002. **Se mantiene lr0 0,001**: rinde igual y converge en la mitad de las épocas. Sin señal de sobreajuste (pérdida de val estable en 0,58). Cifras de la corrida `resultados/prueba_lr001/` (sin pesos versionados). El test no se usó para esta comparación.

Límite: val y test vienen de la misma cámara que train (no hay secuencias repetidas ni imágenes idénticas, comprobado con hashes); las métricas valen para este montaje. En una instalación nueva hay que validar de nuevo.
