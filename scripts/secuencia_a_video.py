"""Arma un video .mp4 desde una secuencia de cuadros de data/ (no hay videos originales en el repo).

Sale en H.264 con el FFmpeg de imageio-ffmpeg (comun.VideoH264), que se reproduce en cualquier lado.
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

from comun import VideoH264, cargar_config, dir_datos, listar_cuadros, ruta_abs  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("seq")
p.add_argument("--fps", type=float, default=None, help="por defecto conteo.fps_cuadros de config.yaml")
p.add_argument("--max", type=int, default=None, help="máximo de cuadros")
p.add_argument("--salida", default=None)
p.add_argument("--config", default=None)
a = p.parse_args()

cfg = cargar_config(a.config)
cuadros = listar_cuadros(dir_datos(cfg) / a.seq / "images")[: a.max]
if not cuadros:
    sys.exit(f"[ERROR] No hay cuadros en {dir_datos(cfg) / a.seq / 'images'}")
fps = a.fps or float(cfg["conteo"]["fps_cuadros"])
salida = Path(a.salida) if a.salida else ruta_abs(cfg["rutas"]["salidas"]) / "videos" / f"{a.seq}.mp4"
alto, ancho = cv2.imread(str(cuadros[0][1])).shape[:2]
video = VideoH264(salida, ancho, alto, fps)
for _, ruta in cuadros:
    video.escribir(cv2.imread(str(ruta)))
video.cerrar()
print(f"[OK] {len(cuadros)} cuadros, {fps:g} fps -> {salida.resolve()}")
