"""Arma el video anotado de una corrida de `uv run tracker procesar`: tubos, línea A, cajas con ID y conteo.

Lee la carpeta del formato común (canales.json, trayectorias.csv, conteos.csv) y el video original.
Cada pez tiene su color (nunca verde) y su ruta; se pone verde cuando ya fue contado. Línea amarilla = línea A.
Arriba, el conteo acumulado de cada tubo.

Uso:
    uv run tracker procesar --video outputs/videos/seq_00015.mp4 --canales canales.json --salida outputs/seq_00015
    uv run python scripts/video_conteo.py outputs/seq_00015 --video outputs/videos/seq_00015.mp4
"""
import argparse
import colorsys
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from comun import VideoH264  # noqa: E402
from tracker import formato  # noqa: E402


def color(i: int) -> tuple[int, int, int]:
    """Color por ID sin tonos verdes (el verde queda para los peces ya contados)."""
    r, g, b = colorsys.hsv_to_rgb((0.5 + 0.55 * ((i * 0.618) % 1)) % 1, 0.85, 1)
    return int(b * 255), int(g * 255), int(r * 255)


p = argparse.ArgumentParser()
p.add_argument("carpeta", help="salida de 'uv run tracker procesar'")
p.add_argument("--video", required=True, help="el mismo video que se procesó")
p.add_argument("--salida", default=None, help="por defecto <carpeta>/anotado.mp4")
a = p.parse_args()

res = formato.leer(a.carpeta)
por_cuadro = defaultdict(list)
for t in res.trayectorias:
    por_cuadro[t["cuadro"]].append(t)
contado_en = {(e["canal"], e["id"]): e["cuadro"] for e in res.eventos}
activos = [c for c in res.canales if c.activo]
salida = Path(a.salida) if a.salida else Path(a.carpeta) / "anotado.mp4"

cap = cv2.VideoCapture(a.video)
if not cap.isOpened():
    sys.exit(f"[ERROR] No se pudo abrir el video: {a.video}")
video = VideoH264(salida, res.meta["ancho"], res.meta["alto"], res.meta["fps"])
ruta, conteo, cuadro = defaultdict(list), {c.id: 0 for c in activos}, 0
while True:
    ok, img = cap.read()
    if not ok:
        break
    for e in res.eventos:
        if e["cuadro"] == cuadro:
            conteo[e["canal"]] = e["conteo"]
    for c in activos:
        x1, y1, x2, y2 = (int(v) for v in c.caja)
        y_a = int(c.y_linea(c.linea_a))
        cv2.rectangle(img, (x1, y1), (x2, y2), (200, 200, 200), 2)
        cv2.line(img, (x1, y_a), (x2, y_a), (0, 255, 255), 3)
    for t in por_cuadro.get(cuadro, []):
        clave = (t["canal"], t["id"])
        ruta[clave].append((int(t["cx"]), int(t["cy"])))
        c = (0, 220, 0) if contado_en.get(clave, 10**9) <= cuadro else color(t["id"])
        cv2.polylines(img, [np.array(ruta[clave], np.int32)], False, c, 2, cv2.LINE_AA)
        cv2.rectangle(img, (int(t["x1"]), int(t["y1"])), (int(t["x2"]), int(t["y2"])), c, 2)
        cv2.putText(img, f"ID {t['id']}", (int(t["x1"]), max(22, int(t["y1"]) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    cv2.rectangle(img, (0, 0), (res.meta["ancho"], 40), (0, 0, 0), -1)
    tubos = " | ".join(f"{c.nombre or c.id}: {conteo[c.id]}" for c in activos)
    cv2.putText(img, f"Cuadro {cuadro} | {tubos} | total: {sum(conteo.values())}", (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    video.escribir(img)
    cuadro += 1
cap.release()
video.cerrar()
print(f"[OK] {cuadro} cuadros -> {salida}")
