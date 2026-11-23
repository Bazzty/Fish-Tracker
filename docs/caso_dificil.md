# Caso difícil: pez perdido justo al cruzar la línea (seq_00015)

> La línea base (YOLO11, `weights/best.pt`, perfil `base`) ya no está en `main`. Para reproducir lo que usa YOLO11 en este documento, usar la rama [`comparacion-yolo11-base`](https://github.com/Bazzty/Fish-Tracker/tree/comparacion-yolo11-base).

Secuencia de validación seq_00015, cuadros 84 a 89 del video armado con `scripts/secuencia_a_video.py` (cuadros consecutivos, numerados desde 0). Es el caso que se vio primero en el diagnóstico de YOLO11 (T11).

## Qué pasa

| Cuadro | Base (YOLO11 + ByteTrack + línea simple) | Variante (YOLO26 + OC-SORT + dos líneas) |
|---|---|---|
| 84 | ID 3, centro en y = 175 | ID 1, y = 176 |
| 85 | ID 3, y = 270 | ID 1, y = 319 |
| 86 | **sin caja** (el pez está sobre la línea A, y = 544) | ID 1, y = 456 |
| 87 | **sin caja** | ID 1, y = 584 (cruza la línea A) |
| 88 | **ID 5**, y = 675 (ya bajo la línea) | ID 1, y = 704: **se cuenta** al llegar a la línea B |
| 89 | ID 5, y = 763 | ID 1, y = 794 |

- **Base:** YOLO11 no detecta al pez en los dos cuadros en que pasa sobre la línea, justo cuando cambia de postura (se curva). ByteTrack termina el ID 3 sobre la línea y crea el ID 5 debajo. Ninguno de los dos cruza la línea, así que el pez **no se cuenta**. En la secuencia completa, contra DAT-02 (referencia 43), la base cuenta 27 peces con IDF1 62,4 % y 11 cambios de ID; la variante, 42 con IDF1 92,4 % y ningún cambio de ID (`uv run tracker evaluar-seguimiento --seq seq_00015 [--perfil base]`).
- **Variante:** YOLO26 detecta al pez en todos los cuadros y OC-SORT mantiene el ID 1. El pez se arma en la línea A y se cuenta una vez al llegar a la B.

## Por qué importa

Es el mecanismo detrás de casi todo el error de la base en test (96 de 132, [tabla](../resultados/tablas/error_conteo_test.md)): la base nunca cuenta de más, solo pierde peces. Un pez que se pierde lejos de la línea no afecta el conteo; uno que se pierde **sobre** la línea, sí. Por eso el cambio que más reduce el error es el tracker, que asocia la reaparición con el ID anterior, más que el detector.

Si aun así el ID se corta, la variante tiene una segunda defensa: la **herencia de estado** (`herencia_cuadros: 15`, `herencia_distancia: 1.5` en `configs/perfiles/variante.yaml`) le pasa al ID nuevo el estado del perdido, de modo que el pez se cuenta una sola vez.

## Cómo reproducirlo

Las capturas no se versionan porque los cuadros del dataset son confidenciales.

```bash
uv run python scripts/secuencia_a_video.py seq_00015
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales cuadro_completo --perfil base --salida outputs/caso_dificil/base
uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales cuadro_completo --perfil variante --salida outputs/caso_dificil/variante
```

Los cuadros 84 a 89 de `outputs/caso_dificil/{base,variante}/anotado.mp4` muestran el caso; los IDs por cuadro están en `seguimiento.json`.
