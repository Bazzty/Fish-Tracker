# Seguimiento y conteo en test

Perfil `variante`: detector YOLO26n (`weights/yolo26.pt`), tracker OC-SORT (`configs/tracker_variante.yaml`) y conteo con dos líneas. Test = 9 secuencias de DAT-01 que no se usaron para entrenar el detector ni para elegir el tracker (el barrido se hizo en val). Se evaluó una sola vez contra las trayectorias de DAT-02, el 22 nov 2026.

Cifras de `resultados/seguimiento_test_variante.json` y `resultados/seguimiento_test_sin_seq00046_variante.json`.

```powershell
uv run tracker evaluar-seguimiento --conjunto test
```

## Total

| | 9 secuencias | 8 secuencias (sin seq_00046) |
|---|---|---|
| Conteo / referencia | 131 / 132 | 90 / 91 |
| Error de conteo | 1 | 1 |
| IDF1 | 93,2 % | 93,9 % |
| Cambios de ID | 4 | 2 |
| MOTA | 87,3 % | 88,0 % |

seq_00046 se reporta aparte porque se usó para diagnosticar los valores de la grilla del barrido (`scripts/barrido_tracker.py`). Sin ella el resultado casi no cambia, así que no infla la cifra.

## Por secuencia

| Secuencia | Conteo | Referencia | Error | IDF1 | Cambios de ID | MOTA |
|---|---|---|---|---|---|---|
| seq_00010 | 13 | 13 | 0 | 91,8 % | 2 | 83,9 % |
| seq_00011 | 21 | 22 | 1 | 95,1 % | 0 | 90,4 % |
| seq_00012 | 10 | 10 | 0 | 94,3 % | 0 | 88,9 % |
| seq_00020 | 11 | 11 | 0 | 92,5 % | 0 | 85,2 % |
| seq_00021 | 7 | 7 | 0 | 93,9 % | 0 | 88,1 % |
| seq_00025 | 3 | 3 | 0 | 97,1 % | 0 | 94,4 % |
| seq_00031 | 10 | 10 | 0 | 93,9 % | 0 | 88,4 % |
| seq_00036 | 15 | 15 | 0 | 93,6 % | 0 | 87,3 % |
| seq_00046 | 41 | 41 | 0 | 91,9 % | 2 | 86,1 % |

## Lectura

- Cuenta bien 8 de 9 secuencias; el único error es un pez de menos en seq_00011.
- Coincide con val (barrido: 135 / 137, IDF1 93,0 %), así que elegir el tracker en val no lo sobreajustó.
- Límites: todas las secuencias son de la misma cámara y la muestra es chica (132 peces). La referencia aplica la misma regla de líneas a DAT-02, así que depende de la posición de la línea A. En otra instalación hay que validar de nuevo.
