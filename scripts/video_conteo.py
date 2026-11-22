"""Rehace el video anotado de una corrida de `uv run tracker procesar` (procesar ya lo deja como anotado.mp4).

Lee la carpeta del conteo (formato común + conteo.json) y el video original, y dibuja tubos, línea A
(amarillo), línea B (naranja, con la regla de dos líneas), cada pez con su ID y su ruta (verde cuando ya fue
contado) y el conteo de cada tubo. Útil si se borró el video o se procesó con --sin-video.

Uso:
    uv run python scripts/video_conteo.py outputs/conteo/yolo26_ocsort/seq_00015/dos_lineas --video outputs/videos/seq_00015.mp4
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tracker import formato  # noqa: E402
from tracker.video import anotar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("carpeta", help="carpeta del conteo que dejó 'uv run tracker procesar'")
p.add_argument("--video", required=True, help="el mismo video que se procesó")
p.add_argument("--salida", default=None, help="por defecto <carpeta>/anotado.mp4")
a = p.parse_args()

conteo_json = Path(a.carpeta) / "conteo.json"
dos_lineas = conteo_json.exists() and \
    json.loads(conteo_json.read_text(encoding="utf-8"))["regla_de_conteo"]["nombre"] == "dos_lineas"
salida = anotar(formato.leer(a.carpeta), a.video, a.salida or Path(a.carpeta) / "anotado.mp4", dos_lineas)
print(f"[OK] Video anotado: {salida.resolve()}")
