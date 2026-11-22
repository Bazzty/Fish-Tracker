# Metodología experimental

## Partición
Por secuencia completa (`configs/split.yaml`): train seq_0001 y seq_0006; val seq_0002; test seq_0003, seq_0004 y seq_0005.
El test se usa una sola vez, al final. Toda decisión (modelo, hiperparámetros, época) se toma con validación.

## Métricas
| Qué | Métrica | Sobre |
|---|---|---|
| Detector | mAP@0.5 (principal), mAP@0.5:0.95, precisión, recall | validación y test |
| Conteo | error absoluto y error relativo contra el conteo manual | test |
| Seguimiento | sin etiquetas: se evalúa solo a través del conteo | test |

## Criterio de éxito
El sistema funciona si, en el conjunto de test:
- **Condición previa (detector):** mAP@0.5 ≥ **0,90** en validación.
- **Criterio principal (conteo):** error relativo del conteo ≤ **10 %** respecto del conteo manual, calculado sobre el total de test (seq_0003, seq_0004 y seq_0005: 25 salmones reales; 10 % equivale a ±2,5 peces). Además se reporta el error de cada secuencia, solo como información y sin umbral, para detectar errores que se compensen entre videos.

Método: un script calcula ambos valores a partir de los pesos entregados. El conteo manual se hace sobre los tramos de test, cuenta los salmones que cruzan la línea virtual.

**Estado de los umbrales: provisionales (hipótesis).** No hay una referencia medida que los respalde todavía.

Regla de revisión (fijada antes de ver resultados):
1. Se ajustan solo con la línea base (YOLO11 preentrenado en COCO, sin entrenar para salmones) y la validación.
2. Si la línea base ya cumple el umbral, se endurece. Si ninguna configuración lo alcanza en validación, se revisa con justificación escrita.
3. Nunca se modifican después de mirar el test.

## Plan de experimentos
Máquina única para toda la grilla (torre con RTX 5070 Ti), semilla fija, mismas épocas y aumentación por defecto.

| Factor | Valores |
|---|---|
| Modelo | YOLO11n, YOLO11s |
| Tamaño de imagen | 640, 960 |
| Tasa de aprendizaje inicial | 0,01 y 0,001 |

8 corridas (grilla completa) más la línea base. Se elige por mAP@0.5 en validación.
Estos valores son una propuesta sin experimentos previos que los validen.

Parámetros fijos e iguales en las 8 corridas (`configs/config.yaml`): hasta 100 épocas con paciencia 20 (una corrida exploratoria de yolo11n con 50 épocas alcanzó su máximo de mAP@0.5 en validación en la época 44 de 50, cerca del tope, por eso se amplió; el early stopping de Ultralytics se evalúa sobre su métrica de ajuste, 0,1·mAP@0.5 + 0,9·mAP@0.5:0.95, y por eso las corridas pueden terminar con distinto número de épocas), lote 16, optimizador SGD explícito (con `auto` Ultralytics ignora `lr0` y elige AdamW, lo que anularía el factor), aumentación por defecto. Selección: mayor mAP@0.5 en validación; diferencias menores a 0,01 se tratan como empate y gana la más simple (n antes que s, 640 antes que 960).

Posición de la línea virtual: factor del conteo, no requiere reentrenar. Se prueban 40, 50 y 60 % del alto (medido desde arriba), con 50 % como valor inicial. Se elige por el error de conteo en validación (seq_0002), nunca en test.

Umbral de asociación de ByteTrack (`match_thresh`): se elige en validación junto con la línea, entre 0,8 (valor por defecto), 0,9 y 0,95. Motivo: con unos 10 cuadros por salmón y cajas de ~271 px de alto, el pez avanza cerca de media caja entre cuadros (más en los saltos), y la asociación por IoU se corta con el umbral por defecto. En una prueba con datos sintéticos y cajas perfectas, el conteo pasó de −24 % (0,8) a −5 % (0,9). Desempate: los valores más cercanos a los por defecto (línea 0,50, match 0,8).

Seguimiento: el detector entrega cajas desde confianza 0,10 porque ByteTrack usa las de 0,10 a 0,25 en su segunda asociación. Si entre dos cuadros faltan más de 10 números (saltos de hasta 114), el seguimiento se reinicia: tras ese salto los peces en pantalla son otros.

Diagnóstico (oráculo): el mismo seguimiento y conteo con las cajas etiquetadas en vez del detector. Si el oráculo cuenta bien y el sistema no, la falla está en el detector; si el oráculo también falla, está en el seguimiento o la línea.

## Riesgos
- GPU RTX 50 (Blackwell): confirmar versión de PyTorch con CUDA compatible antes de entrenar.
- Reproducibilidad: el mAP de los pesos entregados debe coincidir (2 decimales) en otra máquina; verificar en más de un equipo.
- Conteo manual: la dirección está fijada (línea horizontal, cruce de arriba hacia abajo); la posición vertical se elige en validación entre 40, 50 y 60 % del alto.

## Regla de conteo (ampliada antes de evaluar el modelo entrenado)
Hallazgo con el oráculo en validación (seq_0002, 33 peces): la regla original, que cuenta solo el cruce hacia abajo observado entre dos cuadros consecutivos, cuenta de menos (24 a 30 de 33, error de 9 a 27 %, con cajas perfectas). Causas: los saltos de numeración de cuadros (el pez pasa la línea entre cuadros no vistos) y peces que aparecen ya bajo la línea. El Ground Truth cuenta peces únicos, no cruces.

Regla vigente: un ID cuenta una sola vez si cruza la línea hacia abajo, o si su primera observación está en la línea o bajo ella y no se mueve hacia arriba (su última posición no está más arriba que la primera). Con el oráculo en validación el error baja a entre 0 y 9,1 % (las 9 combinaciones de línea y `match_thresh` quedan bajo 10 %). Se probaron además `track_buffer` (30, 60, 120) y `salto_reinicio` (10, 30, sin reinicio) con el oráculo: casi no cambian el conteo, por lo que se mantienen los valores por defecto.

Riesgo conocido: con el detector real, una caja falsa bajo la línea o un pez partido en dos IDs suma de más. Línea y `match_thresh` se eligen en validación con los pesos entrenados, antes de usar test.

## Resultados de la grilla (validación)
Todas las corridas usan seed 42, SGD y los parámetros fijos de arriba; se eligió por mAP@0.5 en validación (seq_0002). Línea base COCO sin entrenar: 0,1516 (yolo11n) y 0,2625 (yolo11s).

| Corrida | Modelo | imgsz | lr0 | Épocas | mAP@0.5 | mAP@0.5:0.95 |
|---|---|---|---|---|---|---|
| R1 | yolo11n | 640 | 0,01 | 45 | 0,9101 | 0,5540 |
| **R2** | **yolo11n** | **640** | **0,001** | **33** | **0,9431** | **0,5849** |
| R3 | yolo11n | 960 | 0,01 | 55 | 0,9080 | 0,5464 |
| R4 | yolo11n | 960 | 0,001 | 57 | 0,9332 | 0,5858 |
| R5 | yolo11s | 640 | 0,01 | 21 | 0,8951 | 0,5351 |
| R6 | yolo11s | 640 | 0,001 | 38 | 0,9491 | 0,5886 |
| R7 | yolo11s | 960 | 0,01 | 80 | 0,8966 | 0,5594 |
| R8 | yolo11s | 960 | 0,001 | 51 | 0,9213 | 0,5878 |

R6 y R2 quedan a menos de 0,01 (0,006), así que por la regla de desempate se elige R2, el modelo más simple. Efecto de cada factor sobre el mAP@0.5 promedio: lr0 0,001 (0,9367) frente a 0,01 (0,9024); imgsz 640 (0,9244) frente a 960 (0,9148); yolo11n (0,9236) frente a yolo11s (0,9155).

Con los pesos de R2 se eligieron en validación línea 0,50 y `match_thresh` 0,8: cuenta 32 de 33 (3,0 %), y las 9 combinaciones probadas quedan bajo 10 %. Bajar `track_high_thresh` y `new_track_thresh` de 0,25 a 0,20 recupera un pez en validación (33 de 33), pero la mejora aparece solo en una mitad de la secuencia y se dejó como mejora futura para no sumar un parámetro ajustado sobre 33 peces.
