"""Prepara las dos versiones de entrenamiento desde configs/split.yaml (única fuente del split).

Comprueba el split (ninguna secuencia en dos conjuntos; val y test solo con DAT-01), escribe
    runs/data_dat01.yaml          train = DAT-01          (versión A)
    runs/data_lab15_dat01.yaml    train = Lab 15 + DAT-01 (versión B)
con el mismo val y test, y la tabla docs/tablas/cuadros_por_split.md con secuencias, cuadros,
cuadros con peces y cajas de cada conjunto. Se usan todos los cuadros (también los sin peces).
No hay azar: con el mismo split.yaml y los mismos datos sale siempre lo mismo.

Uso:
    uv run python scripts/preparar_split.py
    uv run yolo detect train data=runs/data_dat01.yaml model=yolo26n.pt ...
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from comun import RAIZ, cargar_config, dir_datos, escribir_data_yaml, leer_split, listar_cuadros  # noqa: E402


def contar(datos: Path, seqs: list[str]) -> dict:
    """Cuadros, cuadros con peces y cajas de un grupo de secuencias (labels/ al lado de images/)."""
    cuadros = con_peces = cajas = 0
    for s in seqs:
        for _, img in listar_cuadros(datos / s / "images"):
            txt = datos / s / "labels" / f"{img.stem}.txt"
            n = sum(1 for l in txt.read_text(encoding="utf-8").splitlines() if l.strip()) if txt.exists() else 0
            cuadros, con_peces, cajas = cuadros + 1, con_peces + (n > 0), cajas + n
    return dict(secuencias=len(seqs), cuadros=cuadros, con_peces=con_peces, cajas=cajas)


p = argparse.ArgumentParser()
p.add_argument("--config", default=None)
a = p.parse_args()

cfg = cargar_config(a.config)
split = leer_split(cfg)
todas = [s for c in ("train", "val", "test") for s in split[c]]
repetidas = sorted({s for s in todas if todas.count(s) > 1})
if repetidas:
    sys.exit(f"[ERROR] Secuencias en más de un conjunto: {repetidas}")
lab15_fuera = [s for c in ("val", "test") for s in split[c] if s.startswith("lab15_")]
if lab15_fuera:
    sys.exit(f"[ERROR] Lab 15 solo puede ir a train (la validación es solo DAT-01): {lab15_fuera}")

rutas = [escribir_data_yaml(cfg, v) for v in ("dat01", "lab15_dat01")]
datos = dir_datos(cfg)
dat01 = [s for s in split["train"] if not s.startswith("lab15_")]
lab15 = [s for s in split["train"] if s.startswith("lab15_")]
filas = [("A: solo DAT-01", "train", contar(datos, dat01)),
         ("B: Lab 15 + DAT-01", "train", contar(datos, dat01 + lab15)),
         ("A y B", "val", contar(datos, split["val"])),
         ("A y B", "test", contar(datos, split["test"]))]

# Porcentaje sobre el total de DAT-01 (train A + val + test): debe quedar cerca de 70 / 15 / 15.
total = {k: sum(r[k] for v, c, r in filas if not v.startswith("B")) for k in ("cuadros", "cajas")}


def pct(version: str, r: dict, k: str) -> str:
    """'—' en la versión B: su train suma Lab 15 y no es parte del total de DAT-01."""
    return "—" if version.startswith("B") else f"{100 * r[k] / max(total[k], 1):.0f} %"


tabla = ["# Cuadros por split", "",
         "Generado por `scripts/preparar_split.py` desde `configs/split.yaml`. Se usan todos los cuadros.",
         "Los porcentajes son sobre el total de DAT-01 (train de la versión A + val + test);",
         "el reparto buscado es cerca de 70 % / 15 % / 15 %.", "",
         "| Versión | Conjunto | Secuencias | Cuadros | % cuadros | Cuadros con peces | Cajas | % cajas |",
         "|---|---|---|---|---|---|---|---|"]
tabla += [f"| {v} | {c} | {r['secuencias']} | {r['cuadros']} | {pct(v, r, 'cuadros')} | {r['con_peces']} | "
          f"{r['cajas']} | {pct(v, r, 'cajas')} |" for v, c, r in filas]
destino = RAIZ / "docs" / "tablas" / "cuadros_por_split.md"
destino.write_text("\n".join(tabla) + "\n", encoding="utf-8")

print("=" * 72)
print(f"  {'versión':20s} {'conjunto':8s} {'sec':>4s} {'cuadros':>8s} {'%':>5s} {'con peces':>10s} {'cajas':>7s} {'%':>5s}")
for v, c, r in filas:
    print(f"  {v:20s} {c:8s} {r['secuencias']:4d} {r['cuadros']:8d} {pct(v, r, 'cuadros'):>5s} "
          f"{r['con_peces']:10d} {r['cajas']:7d} {pct(v, r, 'cajas'):>5s}")
print("  (% sobre el total de DAT-01; la versión B suma Lab 15 a train)")
for ruta in rutas:
    print(f"  {ruta}")
print(f"  Tabla: {destino}")
print("=" * 72)
