"""Conteo de referencia desde DAT-02: la regla de conteo de la línea base aplicada a las trayectorias etiquetadas.

Es el "tracker perfecto" contra el que se compara el conteo del sistema (docs/formato_comun.md).
Usa el mismo contador que procesar y evaluar-seguimiento (evaluar_seguimiento.conteo_referencia). Sin --canales
cuenta en un solo tubo del tamaño del cuadro, con la línea A en conteo.linea de config.yaml.

Uso:
    uv run python scripts/conteo_referencia.py                        # val y test: imprime la referencia
    uv run python scripts/conteo_referencia.py --guardar              # y la escribe en configs/conteo_real.yaml
    uv run python scripts/conteo_referencia.py --seq seq_00015 --canales dos_tubos --comparar outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml  # noqa: E402

from comun import cargar_config, ruta_abs, secuencias  # noqa: E402
from tracker.canales import cargar_canales, ruta_canales  # noqa: E402
from tracker.evaluar_seguimiento import con_gt, conteo_referencia  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--seq", nargs="+", help="por defecto las de val y test con gt.txt")
p.add_argument("--canales", default=None, help="JSON de tubos, ruta o nombre en configs/ (el mismo de procesar); sin él, un tubo = cuadro")
p.add_argument("--comparar", default=None, help="carpeta de 'tracker procesar' de UNA secuencia")
p.add_argument("--guardar", action="store_true", help="escribir configs/conteo_real.yaml")
p.add_argument("--config", default=None)
a = p.parse_args()

cfg = cargar_config(a.config)
disponibles = con_gt(cfg)
seqs = a.seq or [s for c in ("val", "test") for s in secuencias(cfg, c) if s in disponibles]
if not seqs:
    sys.exit(f"[ERROR] No hay secuencias con gt.txt en {cfg['rutas']['tracking']}")
if a.comparar and len(seqs) != 1:
    sys.exit("[ERROR] --comparar necesita una sola secuencia (--seq).")
canales = cargar_canales(ruta_canales(a.canales)) if a.canales else None

resultado = {}
print("=" * 60)
for seq in seqs:
    resultado[seq] = conteo_referencia(cfg, seq, canales)
    print(f"  {seq:12s} " + " | ".join(f"{c}: {n}" for c, n in resultado[seq].items()))
if a.comparar:
    tracker = json.loads((Path(a.comparar) / "meta.json").read_text(encoding="utf-8"))["conteos"]
    ref = resultado[seqs[0]]
    print("-" * 60)
    print(f"  {'canal':12s} {'tracker':>8s} {'referencia':>11s} {'error':>6s}")
    for c in ref:
        print(f"  {c:12s} {tracker.get(c, 0):8d} {ref[c]:11d} {abs(tracker.get(c, 0) - ref[c]):6d}")
    print(f"  {'total':12s} {sum(tracker.values()):8d} {sum(ref.values()):11d} "
          f"{abs(sum(tracker.values()) - sum(ref.values())):6d}")
if a.guardar:
    ruta = ruta_abs(cfg["rutas"]["conteo_real"])
    texto = ("# Referencia de conteo (DAT-02): regla de la línea base aplicada a las trayectorias etiquetadas,\n"
             f"# un tubo del tamaño del cuadro con la línea A al {float(cfg['conteo']['linea']):.0%} del alto.\n"
             "# Generado por scripts/conteo_referencia.py --guardar; no editar a mano.\n")
    datos = {"conteo_real": {s: sum(n.values()) for s, n in resultado.items()}}
    ruta.write_text(texto + yaml.safe_dump(datos, sort_keys=False), encoding="utf-8")
    print(f"  Guardado: {ruta}")
print("=" * 60)
