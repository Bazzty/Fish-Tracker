"""Genera docs/ejemplo_formato/: carpeta de ejemplo en el formato común para el Validador y la GUI.

ES ILUSTRATIVO: usa el detector, ByteTrack y la regla de línea del Lab 15 (src/contar.py) con 2 canales
(mitades izquierda y derecha del cuadro), solo para tener archivos reales. No es el conteo final:
ese lo implementa tracker.conteo. Los canales no son tubos reales.

Uso:
    uv run python scripts/secuencia_a_video.py seq_00015
    uv run python scripts/generar_ejemplo_formato.py --video outputs/videos/seq_00015.mp4 --desde 120 --cuadros 120
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from comun import cargar_config, ruta_abs  # noqa: E402
from contar import contar_cruces, detectar_fuente, seguir  # noqa: E402
from tracker import formato  # noqa: E402
from tracker.canales import Canal  # noqa: E402
from tracker.pipeline import Resultados, info_video  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--video", required=True)
p.add_argument("--desde", type=int, default=0)
p.add_argument("--cuadros", type=int, default=120)
p.add_argument("--salida", default="docs/ejemplo_formato")
a = p.parse_args()

cfg = cargar_config()
info = info_video(a.video)
fps, ancho, alto = info["fps"], info["ancho"], info["alto"]
canales = [Canal("canal_1", (0, 0, ancho / 2, alto), "Tubo izquierdo"),
           Canal("canal_2", (ancho / 2, 0, ancho, alto), "Tubo derecho")]

dets, _ = detectar_fuente(cfg, video=a.video, pesos=ruta_abs("weights/best.pt"))
dets = [(i, i, c) for i, (_, _, c) in enumerate(dets[a.desde: a.desde + a.cuadros])]  # cuadros desde 0
registros, _ = seguir(cfg, dets)

res = Resultados(meta=dict(video=Path(a.video).name, perfil="base", pesos="weights/best.pt", fps=fps,
                           ancho=ancho, alto=alto, cuadros=len(dets), solo_detectar=False,
                           nota="ejemplo ilustrativo generado con el pipeline del Lab 15"),
                 canales=canales, conteos={c.id: 0 for c in canales})
canal_de_id = {}
for r in registros:  # cada ID pertenece al canal donde apareció primero
    c = next((c for c in canales if c.contiene(r["cx"], r["cy"])), None)
    canal_de_id.setdefault((r["segmento"], r["id"]), c)
for c in canales:
    mias = [r for r in registros if canal_de_id[(r["segmento"], r["id"])] is c]
    for cr in contar_cruces(mias, c.y_linea(c.linea_a)):
        res.conteos[c.id] += 1
        res.eventos.append(dict(canal=c.id, id=cr["id"], cuadro=cr["cuadro"],
                                tiempo_s=round(cr["cuadro"] / fps, 4), conteo=res.conteos[c.id]))
res.eventos.sort(key=lambda e: e["cuadro"])
for n, e in enumerate(res.eventos):  # acumulado por canal en orden temporal
    e["conteo"] = sum(1 for x in res.eventos[: n + 1] if x["canal"] == e["canal"])
for paso, _, cajas in dets:
    for x1, y1, x2, y2, conf in cajas.data[:, :5].tolist():
        c = next((c for c in canales if c.contiene((x1 + x2) / 2, (y1 + y2) / 2)), None)
        res.detecciones.append(dict(cuadro=paso, tiempo_s=round(paso / fps, 4), canal=c.id if c else "",
                                    x1=x1, y1=y1, x2=x2, y2=y2, conf=conf))
for r in registros:
    c = canal_de_id[(r["segmento"], r["id"])]
    if c:
        res.trayectorias.append(dict(cuadro=r["paso"], tiempo_s=round(r["paso"] / fps, 4), canal=c.id,
                                     id=r["id"], x1=r["x1"], y1=r["y1"], x2=r["x2"], y2=r["y2"],
                                     conf=r["conf"], cx=r["cx"], cy=r["cy"]))
salida = formato.exportar(res, ruta_abs(a.salida))
errores = formato.validar(salida)
print(f"[OK] {salida}  conteos {res.conteos}  validación: {'sin errores' if not errores else errores}")
