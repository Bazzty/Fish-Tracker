# Cuadros por split

Generado por `scripts/preparar_split.py` desde `configs/split.yaml`. Se usan todos los cuadros.
Los porcentajes son sobre el total de DAT-01 (train de la versión A + val + test);
el reparto buscado es cerca de 70 % / 15 % / 15 %.

| Versión | Conjunto | Secuencias | Cuadros | % cuadros | Cuadros con peces | Cajas | % cajas |
|---|---|---|---|---|---|---|---|
| A: solo DAT-01 | train | 32 | 11897 | 69 % | 4288 | 7040 | 69 % |
| B: Lab 15 + DAT-01 | train | 38 | 13213 | — | 5413 | 8505 | — |
| A y B | val | 8 | 2718 | 16 % | 915 | 1588 | 16 % |
| A y B | test | 9 | 2587 | 15 % | 932 | 1532 | 15 % |
