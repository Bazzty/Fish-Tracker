# Error de conteo en test: base vs. variante (T19)

> La línea base (YOLO11, `weights/best.pt`, perfil `base`) ya no está en `main`. Para reproducir lo que usa YOLO11 en este documento, usar la rama [`comparacion-yolo11-base`](https://github.com/Bazzty/Fish-Tracker/tree/comparacion-yolo11-base).

## Configuraciones

| Configuración | Pesos | Tracker | Regla de conteo | JSON |
|---|---|---|---|---|
| Base | `weights/best.pt` | bytetrack | linea_simple | `resultados/seguimiento_test_base.json` |
| + YOLO26 | `weights/yolo26.pt` | bytetrack | linea_simple | `resultados/seguimiento_test_yolo26_linea_simple.json` |
| + OC-SORT | `weights/yolo26.pt` | tracker_variante | linea_simple | `resultados/seguimiento_test_yolo26_linea_simple.json` |
| Variante | `weights/yolo26.pt` | tracker_variante | histeresis | `resultados/seguimiento_test_variante.json` |

## Total

| | Base | + YOLO26 | + OC-SORT | Variante |
|---|---|---|---|---|
| Conteo / referencia | 96 / 132 | 91 / 132 | 132 / 132 | 131 / 132 |
| Error neto | 36 | 41 | 0 | 1 |
| Error absoluto (suma por secuencia) | 36 | 41 | 0 | 1 |
| Error relativo | 27,3 % | 31,1 % | 0,0 % | 0,8 % |
| Secuencias con conteo exacto | 0 / 9 | 0 / 9 | 9 / 9 | 8 / 9 |
| IDF1 | 52,0 % | 57,5 % | 93,0 % | 93,2 % |
| Cambios de ID | 43 | 63 | 6 | 4 |

## Por secuencia (conteo; entre paréntesis, el error con signo)

| Secuencia | Referencia | Base | + YOLO26 | + OC-SORT | Variante |
|---|---|---|---|---|---|
| seq_00010 | 13 | 11 (-2) | 9 (-4) | 13 | 13 |
| seq_00011 | 22 | 16 (-6) | 17 (-5) | 22 | 21 (-1) |
| seq_00012 | 10 | 8 (-2) | 8 (-2) | 10 | 10 |
| seq_00020 | 11 | 8 (-3) | 8 (-3) | 11 | 11 |
| seq_00021 | 7 | 4 (-3) | 4 (-3) | 7 | 7 |
| seq_00025 | 3 | 2 (-1) | 2 (-1) | 3 | 3 |
| seq_00031 | 10 | 5 (-5) | 6 (-4) | 10 | 10 |
| seq_00036 | 15 | 14 (-1) | 13 (-2) | 15 | 15 |
| seq_00046 | 41 | 28 (-13) | 24 (-17) | 41 | 41 |

## Cómo se midió

Las 9 secuencias de test, contra las trayectorias de DAT-02, con un solo canal del tamaño del cuadro. Cada columna cambia un componente respecto de la anterior. La variante es la evaluación de test ya registrada en [seguimiento_test.md](seguimiento_test.md).

```bash
uv run tracker evaluar-seguimiento --conjunto test --perfil base
uv run tracker evaluar-seguimiento --conjunto test --perfil variante --conteo linea_simple --trackers configs/bytetrack.yaml configs/tracker_variante.yaml
# copiados a resultados/seguimiento_test_base.json y resultados/seguimiento_test_yolo26_linea_simple.json
uv run tracker comparar "Base=resultados/seguimiento_test_base.json" "+ YOLO26=resultados/seguimiento_test_yolo26_linea_simple.json:bytetrack" "+ OC-SORT=resultados/seguimiento_test_yolo26_linea_simple.json:tracker_variante" "Variante=resultados/seguimiento_test_variante.json" --titulo "Error de conteo en test: base vs. variante (T19)" --salida resultados/tablas/error_conteo_test.md
```

## Lectura

- **La base cuenta de menos en todas las secuencias** (96 de 132, error relativo 27,3 %, sobre el máximo de 10 % del criterio). No cuenta de más en ninguna: el problema no son peces duplicados, sino peces que se pierden.
- **Cambiar solo el detector no ayuda** (91 de 132, y más cambios de ID: 63 contra 43). YOLO26 detecta más peces (recall en val 0,8904 → 0,9673), pero con ByteTrack las trayectorias se siguen cortando.
- **El tracker es el cambio decisivo**: con OC-SORT el error cae a 0 y el IDF1 sube de 57,5 % a 93,0 %. ByteTrack corta la trayectoria cuando el detector falla uno o dos cuadros; si eso pasa justo al cruzar la línea, el pez reaparece con un ID nuevo ya del otro lado y ninguno de los dos IDs cruza la línea completa ([caso difícil](../../docs/caso_dificil.md)). Coincide con el barrido de val ([comparación de trackers](comparacion_trackers.md)), donde ByteTrack queda entre 20 y 32 peces corto.
- **La regla de dos líneas no mejora el conteo en test**: 131 contra 132 con la línea simple (seq_00011, un pez menos). Se mantiene en la variante porque es la que evita contar dos veces a un pez que oscila sobre la línea o que se fragmenta (filtro y herencia), algo que en estas 9 secuencias no ocurrió con OC-SORT. Es una diferencia de un pez y no cambia la conclusión.
