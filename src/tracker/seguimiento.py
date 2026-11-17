"""Seguimiento por canal.

Contrato (lo llama pipeline.procesar una vez por cuadro, en orden):

    seguidor = crear_seguidor(cfg, perfil, canales)
    trayectorias = seguidor.actualizar(cuadro, detecciones)

- 'detecciones': lo que devuelve Detector.detectar (lista de dicts x1, y1, x2, y2, conf).
- Devuelve una fila por pez seguido en ese cuadro, SOLO de canales activos:
      {canal, id, x1, y1, x2, y2, conf, cx, cy}
  'id' es único dentro del canal y no se reutiliza. Un pez cuyo centro cae fuera de todo canal
  activo no genera fila. Debe llamarse también con listas vacías para que los IDs perdidos envejezcan.

Un tracker por canal: cada detección va al canal que contiene su centro. El tipo y su YAML salen del perfil; match_thresh del perfil reemplaza al del YAML.
"""
from typing import Protocol

import numpy as np

from comun import leer_yaml, ruta_abs
from tracker.canales import canal_de


class Seguidor(Protocol):
    def actualizar(self, cuadro: int, detecciones: list[dict]) -> list[dict]: ...


def nuevo_tracker(perfil: dict):
    from ultralytics.trackers.bot_sort import BOTSORT
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.utils import IterableSimpleNamespace

    t = perfil["tracker"]
    args = leer_yaml(ruta_abs(t["config"]))
    args["match_thresh"] = float(t.get("match_thresh", args.get("match_thresh", 0.8)))
    clase = BOTSORT if t["tipo"] == "botsort" else BYTETracker
    return clase(IterableSimpleNamespace(**args))


class SeguidorPorCanal:
    def __init__(self, perfil: dict, canales: list):
        self.canales = canales
        self.trackers = {c.id: nuevo_tracker(perfil) for c in canales}
        self.forma = (int(max(c.caja[3] for c in canales)) + 1, int(max(c.caja[2] for c in canales)) + 1)

    def actualizar(self, cuadro: int, detecciones: list[dict]) -> list[dict]:
        from ultralytics.engine.results import Boxes

        por_canal = {c.id: [] for c in self.canales}
        for d in detecciones:
            c = canal_de(self.canales, (d["x1"] + d["x2"]) / 2, (d["y1"] + d["y2"]) / 2)
            if c:
                por_canal[c.id].append([d["x1"], d["y1"], d["x2"], d["y2"], d["conf"], 0])
        filas = []
        for canal, cajas in por_canal.items():  # también sin cajas: los IDs perdidos envejecen
            datos = np.array(cajas, dtype=np.float32).reshape(-1, 6)
            for x1, y1, x2, y2, tid, conf, *_ in self.trackers[canal].update(Boxes(datos, self.forma)):
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                if canal_de(self.canales, cx, cy) is None:
                    continue
                filas.append(dict(canal=canal, id=int(tid), x1=round(float(x1), 1), y1=round(float(y1), 1),
                                  x2=round(float(x2), 1), y2=round(float(y2), 1), conf=round(float(conf), 4),
                                  cx=round(float(cx), 1), cy=round(float(cy), 1)))
        return filas


def crear_seguidor(cfg: dict, perfil: dict, canales: list) -> Seguidor:
    activos = [c for c in canales if c.activo]
    if not activos:
        raise ValueError("No hay canales activos: marque al menos un tubo.")
    return SeguidorPorCanal(perfil, activos)
