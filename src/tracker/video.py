"""Video anotado de una corrida: tubos, línea A (amarillo), línea B (naranja, regla de dos líneas), cada pez con
su ID y su ruta (verde cuando ya fue contado) y el conteo de cada tubo arriba. Lo usan `tracker procesar` y
scripts/video_conteo.py. Sale en H.264 (FFmpeg de imageio-ffmpeg).
"""
import colorsys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from comun import VideoH264


def color(i: int) -> tuple[int, int, int]:
    """Color por ID sin tonos verdes (el verde queda para los peces ya contados)."""
    r, g, b = colorsys.hsv_to_rgb((0.5 + 0.55 * ((i * 0.618) % 1)) % 1, 0.85, 1)
    return int(b * 255), int(g * 255), int(r * 255)


def anotar(res, video: str | Path, salida: str | Path, dos_lineas: bool = False, fps: float | None = None) -> Path:
    """Dibuja los resultados 'res' (pipeline.Resultados) sobre 'video' y escribe 'salida'. Devuelve la ruta.

    'fps' cambia solo la velocidad de reproducción del video anotado (por defecto, la del video original).
    """
    por_cuadro = defaultdict(list)
    for t in res.trayectorias:
        por_cuadro[t["cuadro"]].append(t)
    contado_en = {(e["canal"], e["id"]): e["cuadro"] for e in res.eventos}
    activos = [c for c in res.canales if c.activo]

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video: {video}")
    salida = Path(salida)
    escritor = VideoH264(salida, res.meta["ancho"], res.meta["alto"], fps or res.meta["fps"])
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
            if dos_lineas:
                y_b = int(c.y_linea(c.linea_b))
                cv2.line(img, (x1, y_b), (x2, y_b), (0, 140, 255), 3)
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
        escritor.escribir(img)
        cuadro += 1
    cap.release()
    escritor.cerrar()
    return salida
