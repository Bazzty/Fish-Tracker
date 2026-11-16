"""Pipeline cíclico por cuadro: leer -> detector -> seguimiento -> conteo por canal -> siguiente cuadro.

    procesar(video, canales, perfil) -> Resultados

Es el contrato entre la GUI (Angelo), el seguimiento y el conteo (Alonso) y la exportación.
'procesar_iter' entrega el avance cuadro a cuadro (para la barra de progreso y el video en vivo);
'procesar' lo consume entero. Con solo_detectar=True corre solo el detector (hoy funciona).
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import cv2

from comun import cargar_config, leer_yaml, ruta_abs
from tracker.canales import Canal, canal_de

PERFILES = "configs/perfiles"


@dataclass
class Avance:
    """Lo que ocurrió en un cuadro. 'imagen' es el cuadro BGR, para mostrarlo en vivo."""
    cuadro: int
    total: int                  # cuadros del video (0 si el contenedor no lo informa)
    tiempo_s: float
    imagen: object
    detecciones: list[dict]
    trayectorias: list[dict]
    eventos: list[dict]
    conteos: dict[str, int]     # acumulado por canal activo; tubo sin peces = 0


@dataclass
class Resultados:
    meta: dict
    canales: list[Canal]
    detecciones: list[dict] = field(default_factory=list)   # {cuadro, tiempo_s, canal, x1, y1, x2, y2, conf}
    trayectorias: list[dict] = field(default_factory=list)  # {cuadro, tiempo_s, canal, id, x1, y1, x2, y2, conf, cx, cy}
    eventos: list[dict] = field(default_factory=list)       # {canal, id, cuadro, tiempo_s, conteo}
    conteos: dict[str, int] = field(default_factory=dict)


def cargar_perfil(perfil: str | Path | dict | None = None) -> dict:
    """Perfil por nombre ('base', 'variante'), por ruta a un YAML o ya cargado. Por defecto, 'base'."""
    if isinstance(perfil, dict):
        return perfil
    nombre = str(perfil or "base")
    ruta = Path(nombre) if nombre.endswith(".yaml") else ruta_abs(f"{PERFILES}/{nombre}.yaml")
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el perfil '{nombre}' ({ruta})")
    return leer_yaml(ruta)


def info_video(video: str | Path) -> dict:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    info = dict(ancho=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), alto=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                cuadros=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), fps=float(fps) if fps and fps > 0 else 10.0)
    cap.release()
    return info


def _validar_canales(canales: list[Canal], solo_detectar: bool) -> list[Canal]:
    activos = [c for c in canales if c.activo]
    if not solo_detectar and not activos:
        raise ValueError("No hay canales activos: marque al menos un tubo.")
    if len({c.id for c in canales}) != len(canales):
        raise ValueError("Hay ids de canal repetidos.")
    return activos


def procesar_iter(video: str | Path, canales: list[Canal], perfil=None, solo_detectar: bool = False,
                  cfg: dict | None = None) -> Iterator[Avance]:
    """Generador de Avance. El último Avance trae los conteos finales."""
    cfg = cfg or cargar_config()
    perfil = cargar_perfil(perfil)
    activos = _validar_canales(canales, solo_detectar)
    info = info_video(video)

    from tracker.detector import Detector

    detector = Detector(cfg, perfil)
    seguidor = contador = None
    if not solo_detectar:
        from tracker.conteo import crear_contador
        from tracker.seguimiento import crear_seguidor

        seguidor = crear_seguidor(cfg, perfil, activos)
        contador = crear_contador(cfg, perfil, activos, info["fps"])

    cap = cv2.VideoCapture(str(video))
    try:
        cuadro = 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            dets = detector.detectar(img)
            tray = seguidor.actualizar(cuadro, dets) if seguidor else []
            eventos = contador.actualizar(cuadro, tray) if contador else []
            conteos = contador.conteos() if contador else {c.id: 0 for c in activos}
            yield Avance(cuadro, info["cuadros"], cuadro / info["fps"], img, dets, tray, eventos, conteos)
            cuadro += 1
    finally:
        cap.release()


def procesar(video: str | Path, canales: list[Canal], perfil=None, solo_detectar: bool = False,
             al_avanzar: Callable[[Avance], None] | None = None, cfg: dict | None = None) -> Resultados:
    """Procesa el video completo. 'al_avanzar' recibe cada Avance (progreso en vivo)."""
    perfil_cargado = cargar_perfil(perfil)
    info = info_video(video)
    activos = [c for c in canales if c.activo]
    res = Resultados(meta={}, canales=canales, conteos={c.id: 0 for c in activos})
    for av in procesar_iter(video, canales, perfil_cargado, solo_detectar, cfg):
        for d in av.detecciones:
            c = canal_de(canales, (d["x1"] + d["x2"]) / 2, (d["y1"] + d["y2"]) / 2)
            res.detecciones.append(dict(cuadro=av.cuadro, tiempo_s=round(av.tiempo_s, 4),
                                        canal=c.id if c else "", **d))
        res.trayectorias += [dict(cuadro=av.cuadro, tiempo_s=round(av.tiempo_s, 4), **t) for t in av.trayectorias]
        res.eventos += av.eventos
        res.conteos = av.conteos
        if al_avanzar:
            al_avanzar(av)
    res.meta = dict(video=Path(video).name, perfil=perfil_cargado.get("nombre", "?"),
                    pesos=perfil_cargado["detector"]["pesos"], fps=info["fps"], ancho=info["ancho"],
                    alto=info["alto"], cuadros=info["cuadros"], solo_detectar=solo_detectar)
    return res
