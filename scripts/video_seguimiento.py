"""Arma un video .mp4 con el seguimiento dibujado: caja e ID de cada pez y la ruta que recorre.

Lee las trayectorias que deja `uv run tracker evaluar-seguimiento`. Cada ID tiene su color;
si un pez cambia de color a mitad de camino, ahí el tracker le dio un ID nuevo (IDSW).

Uso:
    uv run python scripts/video_seguimiento.py seq_00015                       # bytetrack, perfil base
    uv run python scripts/video_seguimiento.py seq_00015 --tracker botsort
    uv run python scripts/video_seguimiento.py seq_00015 --oraculo
"""
import argparse
import colorsys
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from comun import VideoH264, cargar_config, ruta_abs  # noqa: E402
from tracker.evaluar_seguimiento import VACIO, cuadros_seq, leer_mot  # noqa: E402


def color(i: int) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb((i * 0.618) % 1, 0.85, 1)
    return int(b * 255), int(g * 255), int(r * 255)


p = argparse.ArgumentParser()
p.add_argument("seq")
p.add_argument("--tracker", default="bytetrack", help="nombre del YAML usado (bytetrack, botsort)")
p.add_argument("--perfil", default="base")
p.add_argument("--oraculo", action="store_true", help="trayectorias de la corrida con --oraculo")
p.add_argument("--fps", type=float, default=None, help="por defecto conteo.fps_cuadros de config.yaml")
p.add_argument("--config", default=None)
p.add_argument("--salida", default=None)
a = p.parse_args()

cfg = cargar_config(a.config)
corrida = ruta_abs(cfg["rutas"]["salidas"]) / "evaluacion_seguimiento" / (a.perfil + ("_oraculo" if a.oraculo else ""))
ruta_pred = corrida / "trayectorias" / a.tracker / f"{a.seq}.txt"
if not ruta_pred.exists():
    sys.exit(f"[ERROR] No existe {ruta_pred}. Ejecute antes: uv run tracker evaluar-seguimiento --seq {a.seq}"
             + (" --oraculo" if a.oraculo else ""))
pred = leer_mot(ruta_pred)
cuadros = cuadros_seq(cfg, a.seq)
fps = a.fps or float(cfg["conteo"]["fps_cuadros"])
salida = Path(a.salida) if a.salida else ruta_abs(cfg["rutas"]["salidas"]) / "videos" / (
    f"{a.seq}_{a.tracker}" + ("_oraculo" if a.oraculo else "") + ".mp4")
salida.parent.mkdir(parents=True, exist_ok=True)

alto, ancho = cv2.imread(str(cuadros[0][1])).shape[:2]
video = VideoH264(salida, ancho, alto, fps)
ruta = defaultdict(list)  # id -> centros recorridos
for f, imagen in cuadros:
    img = cv2.imread(str(imagen))
    cajas = pred.get(f, VACIO)
    for i, x, y, w, h in cajas:
        ruta[int(i)].append((int(x + w / 2), int(y + h / 2)))
    for i, x, y, w, h in cajas:
        c = color(int(i))
        cv2.polylines(img, [np.array(ruta[int(i)], np.int32)], False, c, 2, cv2.LINE_AA)
        cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), c, 2)
        cv2.circle(img, ruta[int(i)][-1], 4, c, -1)
        cv2.putText(img, f"ID {int(i)}", (int(x), max(22, int(y) - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    cv2.rectangle(img, (0, 0), (ancho, 40), (0, 0, 0), -1)
    cv2.putText(img, f"Cuadro {f} | peces seguidos: {len(cajas)} | IDs hasta ahora: {len(ruta)}",
                (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    video.escribir(img)
video.cerrar()
print(f"[OK] {len(cuadros)} cuadros, {fps:g} fps -> {salida}")
