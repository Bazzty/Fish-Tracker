"""Arma un video .mp4 desde una secuencia de cuadros de data/ (no hay videos originales en el repo).

Los saltos de numeración de la secuencia no se conservan: los cuadros quedan consecutivos.

Uso:
    uv run python scripts/secuencia_a_video.py seq_00015            # -> outputs/videos/seq_00015.mp4
    uv run python scripts/secuencia_a_video.py seq_00015 --max 60 --fps 10
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2  # noqa: E402

from comun import cargar_config, dir_datos, listar_cuadros, ruta_abs  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("seq")
p.add_argument("--fps", type=float, default=None, help="por defecto conteo.fps_cuadros de config.yaml")
p.add_argument("--max", type=int, default=None, help="máximo de cuadros")
p.add_argument("--salida", default=None)
a = p.parse_args()

cfg = cargar_config()
cuadros = listar_cuadros(dir_datos(cfg) / a.seq / "images")[: a.max]
fps = a.fps or float(cfg["conteo"]["fps_cuadros"])
salida = Path(a.salida) if a.salida else ruta_abs(cfg["rutas"]["salidas"]) / "videos" / f"{a.seq}.mp4"
salida.parent.mkdir(parents=True, exist_ok=True)
primero = cv2.imread(str(cuadros[0][1]))
alto, ancho = primero.shape[:2]
out = cv2.VideoWriter(str(salida), cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto))
for _, ruta in cuadros:
    out.write(cv2.imread(str(ruta)))
out.release()
print(f"[OK] {len(cuadros)} cuadros, {fps:g} fps -> {salida}")
