"""Genera docs/ejemplo_formato/: carpeta de ejemplo SINTÉTICA en el formato común.

No usa datos del curso ni del cliente: las cajas y trayectorias son inventadas y deterministas.
Dos canales: canal_1 con 2 peces que cruzan la zona de conteo y canal_2 vacío (conteo 0),
más una detección fuera de todo canal (columna 'canal' vacía).

Uso:
    uv run python scripts/generar_ejemplo_formato.py
    uv run tracker validar docs/ejemplo_formato
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from comun import ruta_abs  # noqa: E402
from tracker import formato  # noqa: E402
from tracker.canales import Canal  # noqa: E402
from tracker.pipeline import Resultados  # noqa: E402

FPS, ANCHO, ALTO, CUADROS = 10.0, 1280, 720, 60
canales = [Canal("canal_1", (100, 0, 500, 720), "Tubo 1"),
           Canal("canal_2", (700, 0, 1100, 720), "Tubo 2")]
# (id, cuadro de entrada, x del centro, velocidad en px/cuadro, ancho, alto, confianza)
peces = [(1, 0, 300, 18.0, 120, 160, 0.91), (2, 20, 260, 15.0, 110, 150, 0.84)]

res = Resultados(meta=dict(video="ejemplo_sintetico.mp4", perfil="base", pesos="weights/best.pt", fps=FPS,
                           ancho=ANCHO, alto=ALTO, cuadros=CUADROS, solo_detectar=False,
                           nota="ejemplo sintético: cajas inventadas, no provienen de ningún video"),
                 canales=canales, conteos={c.id: 0 for c in canales})
canal = canales[0]
y_a = canal.y_linea(canal.linea_a)
previo = {}
for cuadro in range(CUADROS):
    t = round(cuadro / FPS, 4)
    for pid, entra, cx, v, w, h, conf in peces:
        cy = -h / 2 + v * (cuadro - entra)
        if cuadro < entra or cy - h / 2 > ALTO:
            continue
        caja = dict(x1=cx - w / 2, y1=max(0.0, cy - h / 2), x2=cx + w / 2, y2=min(float(ALTO), cy + h / 2))
        cyc = (caja["y1"] + caja["y2"]) / 2
        res.detecciones.append(dict(cuadro=cuadro, tiempo_s=t, canal=canal.id, **caja, conf=conf))
        if cyc < 0:
            continue
        res.trayectorias.append(dict(cuadro=cuadro, tiempo_s=t, canal=canal.id, id=pid, **caja, conf=conf,
                                     cx=float(cx), cy=cyc))
        if pid in previo and previo[pid] < y_a <= cyc:
            res.conteos[canal.id] += 1
            res.eventos.append(dict(canal=canal.id, id=pid, cuadro=cuadro, tiempo_s=t,
                                    conteo=res.conteos[canal.id]))
        previo[pid] = cyc
    if cuadro == 30:  # reflejo fuera de los tubos: se detecta pero no pertenece a ningún canal
        res.detecciones.append(dict(cuadro=cuadro, tiempo_s=t, canal="", x1=580.0, y1=300.0, x2=640.0,
                                    y2=360.0, conf=0.22))

salida = formato.exportar(res, ruta_abs("docs/ejemplo_formato"))
errores = formato.validar(salida)
print(f"[OK] {salida}  conteos {res.conteos}  validación: {'sin errores' if not errores else errores}")
