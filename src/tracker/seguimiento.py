"""Seguimiento por canal.  RESPONSABLE: Alonso (semana 1: ByteTrack por canal; semana 2: ajuste y otros trackers).

Contrato (lo llama pipeline.procesar una vez por cuadro, en orden):

    seguidor = crear_seguidor(cfg, perfil, canales)
    trayectorias = seguidor.actualizar(cuadro, detecciones, imagen)

- 'detecciones': lo que devuelve Detector.detectar (lista de dicts x1, y1, x2, y2, conf).
- 'imagen': el cuadro BGR. La usan los trackers que miran la apariencia de cada pez (DeepSORT y BoT-SORT
  con ReID); los demás la ignoran.
- Devuelve una fila por pez seguido en ese cuadro, SOLO de canales activos:
      {canal, id, x1, y1, x2, y2, conf, cx, cy}
  'id' es único dentro del canal y no se reutiliza. Un pez cuyo centro cae fuera de todo canal
  activo no genera fila. Debe llamarse también con listas vacías para que los IDs perdidos envejezcan.

Un tracker por canal: cada detección va al canal que contiene su centro. El YAML sale del perfil
(tracker.config) y el tipo, de su tracker_type (si no lo trae, de tracker.tipo):
    bytetrack  ByteTrack de Ultralytics        configs/bytetrack.yaml   (match_thresh del perfil si el YAML no lo trae)
    botsort    BoT-SORT de Ultralytics         configs/botsort.yaml     (match_thresh del YAML)
               con ReID                        configs/botsort_reid.yaml (necesita la imagen; describe cada pez
                                                                        con los pesos del detector del perfil)
    ocsort     OC-SORT de Roboflow 'trackers'  configs/ocsort.yaml      (necesita Python >= 3.11)
    deepsort   DeepSORT de deep-sort-realtime  configs/deepsort.yaml    (necesita la imagen)
"""
from pathlib import Path
from typing import Protocol

import numpy as np

from comun import leer_yaml, ruta_abs
from tracker.canales import canal_de

TIPOS = ("bytetrack", "botsort", "ocsort", "deepsort")


class Seguidor(Protocol):
    def actualizar(self, cuadro: int, detecciones: list[dict], imagen: np.ndarray | None = None) -> list[dict]: ...


# ----------------------------------------------------------------------------- un tracker
# Cada clase recibe las cajas del canal (N x 5: x1, y1, x2, y2, conf) y devuelve (x1, y1, x2, y2, id, conf)
# de los peces seguidos en ese cuadro.

class _Ultralytics:
    """ByteTrack o BoT-SORT de Ultralytics. BoT-SORT con with_reid usa model: detector = pesos del detector."""

    def __init__(self, tipo: str, args: dict, match_thresh: float | None, pesos_detector: str | None):
        from ultralytics.trackers.bot_sort import BOTSORT
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.utils import IterableSimpleNamespace

        if "match_thresh" not in args:  # si el YAML no lo fija, manda el del perfil (Lab 15: se elige en validación)
            args["match_thresh"] = float(match_thresh if match_thresh is not None else 0.8)
        self.reid = tipo == "botsort" and bool(args.get("with_reid"))
        if self.reid:
            if args.get("model", "detector") in ("detector", "auto"):  # 'auto' necesita al detector dentro del tracker
                if not pesos_detector:
                    raise ValueError("BoT-SORT con ReID usa los pesos del detector, pero el perfil no los indica.")
                args["model"] = str(ruta_abs(pesos_detector))
            if not Path(args["model"]).exists():
                raise FileNotFoundError(f"No se encontraron los pesos para el ReID: {args['model']}")
        self.t = (BOTSORT if tipo == "botsort" else BYTETracker)(IterableSimpleNamespace(**args))

    def paso(self, cajas: np.ndarray, imagen, forma: tuple[int, int]):
        from ultralytics.engine.results import Boxes

        if self.reid and imagen is None:
            raise ValueError("BoT-SORT con ReID necesita la imagen de cada cuadro (usa la apariencia de los peces).")
        datos = np.zeros((len(cajas), 6), dtype=np.float32)
        datos[:, :5] = cajas
        for x1, y1, x2, y2, tid, conf, *_ in self.t.update(Boxes(datos, forma), imagen):
            yield x1, y1, x2, y2, tid, conf


class _OCSort:
    """OC-SORT de la librería 'trackers' (Roboflow)."""

    def __init__(self, args: dict):
        try:
            from trackers import OCSORTTracker
        except ImportError:
            raise ValueError("OC-SORT necesita la librería 'trackers' (Python >= 3.11): uv sync") from None
        self.t = OCSORTTracker(**args)

    def paso(self, cajas: np.ndarray, imagen, forma):
        import supervision as sv

        r = self.t.update(sv.Detections(xyxy=cajas[:, :4].astype(np.float32), confidence=cajas[:, 4].astype(np.float32),
                                        class_id=np.zeros(len(cajas), dtype=int)))
        conf = r.confidence if r.confidence is not None else np.ones(len(r))
        for (x1, y1, x2, y2), tid, c in zip(r.xyxy, r.tracker_id, conf):
            if tid >= 0:  # -1 = aún no confirmado
                yield x1, y1, x2, y2, tid, c


class _DeepSort:
    """DeepSORT de deep-sort-realtime: movimiento + apariencia (MobileNet, pesos incluidos en el paquete)."""

    def __init__(self, args: dict):
        import warnings

        import torch

        gpu = torch.cuda.is_available()
        with warnings.catch_warnings():  # la librería importa pkg_resources al crear MobileNet (aviso inofensivo)
            warnings.simplefilter("ignore", UserWarning)
            from deep_sort_realtime.deepsort_tracker import DeepSort

            self.t = DeepSort(embedder="mobilenet", embedder_gpu=gpu, half=gpu, bgr=True, **args)

    def paso(self, cajas: np.ndarray, imagen, forma):
        if imagen is None:
            raise ValueError("DeepSORT necesita la imagen de cada cuadro (usa la apariencia de los peces).")
        crudas = [([x1, y1, x2 - x1, y2 - y1], conf, 0) for x1, y1, x2, y2, conf in cajas]
        for t in self.t.update_tracks(crudas, frame=imagen):
            if t.is_confirmed() and t.time_since_update == 0:  # solo los vistos en este cuadro
                x1, y1, x2, y2 = t.to_ltrb(orig=True)
                yield x1, y1, x2, y2, int(t.track_id), t.get_det_conf() or 1.0


def con_tracker(perfil: dict, config: str) -> dict:
    """Copia del perfil con otro tracker: el tipo sale de tracker_type del YAML (p. ej. configs/ocsort.yaml)."""
    ruta = ruta_abs(config)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la configuración del tracker: {config}")
    tipo = leer_yaml(ruta).get("tracker_type", "bytetrack")
    return {**perfil, "nombre": f"{perfil.get('nombre', 'perfil')}_{ruta.stem}",
            "tracker": {**perfil.get("tracker", {}), "tipo": tipo, "config": str(config)}}


def tipo_y_args(perfil: dict) -> tuple[str, dict]:
    """Tipo del tracker (tracker_type del YAML; si no lo trae, tracker.tipo del perfil) y sus parámetros."""
    t = perfil["tracker"]
    ruta = ruta_abs(t["config"])
    if not ruta.exists():
        raise FileNotFoundError(f"No existe la configuración del tracker: {t['config']}")
    yaml = leer_yaml(ruta)
    tipo = str(yaml.get("tracker_type", t.get("tipo", "bytetrack"))).lower()
    if tipo not in TIPOS:
        raise ValueError(f"Tracker '{tipo}' no soportado (use {', '.join(TIPOS)}).")
    return tipo, {k: v for k, v in yaml.items() if k != "tracker_type"}


def necesita_imagen(perfil: dict) -> bool:
    """True si el tracker del perfil mira la apariencia (DeepSORT, o BoT-SORT con with_reid)."""
    tipo, args = tipo_y_args(perfil)
    return tipo == "deepsort" or (tipo == "botsort" and bool(args.get("with_reid")))


def nuevo_tracker(perfil: dict):
    t = perfil["tracker"]
    tipo, args = tipo_y_args(perfil)
    if tipo in ("bytetrack", "botsort"):
        pesos = perfil.get("detector", {}).get("pesos")
        return _Ultralytics(tipo, {**args, "tracker_type": tipo}, t.get("match_thresh"), pesos)
    return _OCSort(args) if tipo == "ocsort" else _DeepSort(args)


# ----------------------------------------------------------------------------- por canal
class SeguidorPorCanal:
    def __init__(self, perfil: dict, canales: list):
        self.canales = canales
        self.trackers = {c.id: nuevo_tracker(perfil) for c in canales}
        self.forma = (int(max(c.caja[3] for c in canales)) + 1, int(max(c.caja[2] for c in canales)) + 1)

    def actualizar(self, cuadro: int, detecciones: list[dict], imagen: np.ndarray | None = None) -> list[dict]:
        por_canal = {c.id: [] for c in self.canales}
        for d in detecciones:
            c = canal_de(self.canales, (d["x1"] + d["x2"]) / 2, (d["y1"] + d["y2"]) / 2)
            if c:
                por_canal[c.id].append([d["x1"], d["y1"], d["x2"], d["y2"], d["conf"]])
        filas = []
        for canal, cajas in por_canal.items():  # también sin cajas: los IDs perdidos envejecen
            cajas = np.array(cajas, dtype=np.float32).reshape(-1, 5)
            for x1, y1, x2, y2, tid, conf in self.trackers[canal].paso(cajas, imagen, self.forma):
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
