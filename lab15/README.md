# Archivo del Lab 15

Esta carpeta guarda el material del **Lab 15**, del que salió la línea base de la Solemne 3. Sus cifras usan la **partición antigua de 6 secuencias** y no valen para la Solemne 3. Para el sistema actual, ver el [README principal](../README.md).

- `metodologia.md`: métricas, criterio de éxito y plan de experimentos del Lab 15.
- `analysis/Analisis_000X.txt`: conteo manual de salmones por secuencia (Avance 1).

Los scripts `entorno.py`, `grilla.py`, `contar.py`, `criterio.py`, `analisis.py` y `visualizador.py` se quitaron del repositorio. Siguen en el historial de git, antes del commit «chore: quitar scripts y resultados del Lab 15».

## Diseño

```
Video → Lectura → Detector (YOLO11) → Seguimiento (ByteTrack) → Conteo (línea virtual) → Video anotado + conteo
```

- **Detector: YOLO11, tamaños n (base) y s (comparación).** Detector de un solo pase que entrena con las etiquetas YOLO tal cual vienen. Los salmones son grandes (mediana ~3,7 % de la imagen) y hay pocos por cuadro, por lo que un modelo pequeño debería bastar.
  Fuentes: [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11); Redmon et al., [You Only Look Once](https://arxiv.org/abs/1506.02640).
- **Seguimiento: ByteTrack.** Asocia casi todas las cajas, incluidas las de baja confianza (el detector entrega desde 0,10), para reducir trayectorias fragmentadas. `match_thresh` se eligió en validación (0,8).
  Fuentes: Zhang et al., [ByteTrack](https://arxiv.org/abs/2110.06864); [Ultralytics Track](https://docs.ultralytics.com/modes/track/).
- **Conteo: cruce de línea virtual.** Cámara fija desde arriba; los salmones bajan en vertical. Línea horizontal al 50 % del alto, elegida en validación entre 40, 50 y 60 %. Cada ID se cuenta una sola vez.
  Fuente: [Ultralytics Object Counting](https://docs.ultralytics.com/guides/object-counting/).
- **Video: OpenCV** ([VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html), [VideoWriter](https://docs.opencv.org/4.x/dd/d9e/classcv_1_1VideoWriter.html)).

Limitación: ByteTrack se evalúa en benchmarks de personas y ningún paper citado trata salmones.

## Partición antigua

| Conjunto | Secuencias | Cuadros | Uso |
|---|---|---|---|
| Train | seq_0001, seq_0006 | 856 (65 %) | entrenar |
| Val | seq_0002 | 242 (18 %) | elegir hiperparámetros y modelo |
| Test | seq_0003, seq_0004, seq_0005 | 218 (17 %) | evaluación final, una sola vez |

En la Solemne 3 estas secuencias son `data/lab15_sec1` … `lab15_sec6` y van solo a entrenamiento (ver `configs/split.yaml`).

## Resultados presentados

Pesos `weights/best.pt` (corrida R2: yolo11n, imgsz 640, lr0 0.001, SGD; sha256 `c384a62e…a2f8`).

| Qué | Valor (partición antigua) |
|---|---|
| mAP@0.5 en validación | 0,9431 |
| mAP@0.5 en test | 0,9685 (`resultados/evaluacion_test_best.json`) |

En la validación nueva de la Solemne 3 el mismo detector da mAP@50 0,9436 ([tabla](../resultados/tablas/map50_yolo11_val.md)).

Reentrenar la configuración R2 (con la partición actual, no la antigua):

```powershell
uv run python src/entrenamiento/entrenar.py --modelo yolo11n.pt --imgsz 640 --lr0 0.001 --nombre R2
```
