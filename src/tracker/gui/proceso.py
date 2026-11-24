"""Procesamiento en segundo plano (T15) y mensajes de error claros (T17).

HiloProceso corre tracker.pipeline.procesar en un QThread para que la ventana no se congele.
Emite el avance cuadro a cuadro (video con cajas + conteo en vivo) y al final el Resultados.
"""
from __future__ import annotations

import dataclasses
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal


GPU_NO_SOPORTADA = "no está soportada por"

# La GUI usa un solo perfil: la variante (YOLO26 + conteo A -> B). Su definición (pesos, umbrales, tracker)
# está en configs/perfiles/variante.yaml.
PERFIL = "variante"


def nombre_modelo(perfil: str | None = None) -> str:
    """Solo el modelo del perfil, p. ej. «YOLO26» (sale del nombre del archivo de pesos)."""
    perfil = perfil or PERFIL
    try:
        from tracker.pipeline import cargar_perfil

        return Path(cargar_perfil(perfil)["detector"]["pesos"]).stem.upper()
    except Exception:  # sin repo o perfil ilegible: que la barra no falle
        return f"perfil '{perfil}'"


def descripcion_modelo(perfil: str | None = None) -> str:
    """Modelo y regla de conteo del perfil, p. ej. «YOLO26 · conteo A→B» (para tooltip y mensajes)."""
    perfil = perfil or PERFIL
    try:
        from tracker.pipeline import cargar_perfil

        p = cargar_perfil(perfil)
        modelo = nombre_modelo(perfil)
        tipo = p.get("conteo", {}).get("tipo", "?")
        regla = {"histeresis": "conteo A→B", "linea_simple": "conteo con línea simple"}.get(tipo, f"conteo {tipo}")
        return f"{modelo} · {regla}"
    except Exception:  # sin repo o perfil ilegible: que la barra no falle
        return f"perfil '{perfil}'"


class _Cancelado(Exception):
    """Se lanza dentro del callback del pipeline para abortar el procesamiento."""


def listar_perfiles() -> list[str]:
    """Perfiles disponibles (configs/perfiles/*.yaml), con 'base' primero."""
    try:
        from comun import ruta_abs

        nombres = sorted(p.stem for p in ruta_abs("configs/perfiles").glob("*.yaml"))
    except Exception:  # sin repo o sin dependencias: valores por defecto
        nombres = []
    nombres = nombres or ["base", "variante"]
    return sorted(nombres, key=lambda n: (n != "base", n))


def mensaje_de_error(e: BaseException) -> str:
    """Convierte una excepción del pipeline en un mensaje que se entienda sin leer código."""
    texto = str(e.code) if isinstance(e, SystemExit) else str(e)
    if isinstance(e, SystemExit):  # p. ej. GPU no soportada (comun.verificar_gpu)
        texto = texto.replace("[ERROR] ", "")
        if GPU_NO_SOPORTADA in texto:
            # «uv sync» no lo arregla: la GPU es demasiado antigua para este PyTorch
            texto = texto.split(" Instale torch")[0]
            return (f"{texto}\n\nTu GPU no sirve con la versión de PyTorch del proyecto. "
                    "Elige «CPU» en Dispositivo (barra de arriba) y vuelve a procesar: es más lento, pero funciona.")
        return texto
    if isinstance(e, FileNotFoundError):
        if "pesos" in texto.lower():
            return f"{texto}\n\nRevisa que el archivo exista en la carpeta weights/ (ver README, sección pesos)."
        return texto
    if isinstance(e, NotImplementedError):
        return (f"Esta parte aún no está implementada en el perfil «{PERFIL}»:\n{texto}\n\n"
                "Revisa que tengas la última versión del repositorio (git merge origin/develop) o consulta con quien la implementa.")
    if isinstance(e, ImportError):
        return f"Falta una librería del proyecto: {texto}\n\nEjecuta `uv sync` y vuelve a abrir la aplicación."
    if isinstance(e, ValueError):
        return texto
    return f"Error inesperado ({type(e).__name__}): {texto}"


class RenumeradorIds:
    """IDs consecutivos por tubo (1, 2, 3…) en orden de aparición.

    Los IDs de ByteTrack salen de un contador global: lo comparten todos los tubos y se gasta en cada
    falso positivo, por eso saltan (1, 7, 12…). Un ID solo es una etiqueta; renumerarlo de forma
    consistente (trayectorias y conteos) no cambia a qué pez corresponde.
    """

    def __init__(self) -> None:
        self.mapa: dict[tuple[str, int], int] = {}
        self._sig: dict[str, int] = {}

    def id(self, canal: str, tid: int) -> int:
        k = (canal, tid)
        if k not in self.mapa:
            self._sig[canal] = self._sig.get(canal, 0) + 1
            self.mapa[k] = self._sig[canal]
        return self.mapa[k]

    def registrar(self, av) -> None:
        """Llamar en orden, con cada cuadro (también los que no se muestran)."""
        for t in av.trayectorias:
            self.id(t["canal"], t["id"])
        for e in av.eventos:
            self.id(e["canal"], e["id"])

    def avance(self, av):
        """Copia del Avance con los IDs renumerados (para mostrar en vivo)."""
        return dataclasses.replace(
            av,
            trayectorias=[{**t, "id": self.id(t["canal"], t["id"])} for t in av.trayectorias],
            eventos=[{**e, "id": self.id(e["canal"], e["id"])} for e in av.eventos],
        )

    def resultados(self, res) -> None:
        res.trayectorias = [{**t, "id": self.id(t["canal"], t["id"])} for t in res.trayectorias]
        res.eventos = [{**e, "id": self.id(e["canal"], e["id"])} for e in res.eventos]
        res.meta["nota_ids"] = "IDs renumerados por canal (1, 2, 3…) en orden de aparición."


class HiloProceso(QThread):
    avance = Signal(object)  # tracker.pipeline.Avance (a lo más ~25 por segundo)
    terminado = Signal(object)  # tracker.pipeline.Resultados
    fallo = Signal(str)  # mensaje ya legible
    cancelado = Signal()

    def __init__(self, video: str, canales: list, perfil: str, parent=None, dispositivo: str = "auto") -> None:
        super().__init__(parent)
        self.video, self.canales, self.perfil = video, canales, perfil
        self.dispositivo = dispositivo  # "auto" (GPU si sirve) o "cpu"
        self._cancelar = False

    def cancelar(self) -> None:
        self._cancelar = True

    def run(self) -> None:
        try:
            from tracker.pipeline import procesar

            cfg = None
            if self.dispositivo != "auto":  # no se toca configs/config.yaml (archivo compartido)
                from comun import cargar_config

                cfg = cargar_config()
                cfg.setdefault("proyecto", {})["dispositivo"] = self.dispositivo

            ultimo = [0.0]
            ids = RenumeradorIds()

            def al_avanzar(av) -> None:
                if self._cancelar:
                    raise _Cancelado()
                ids.registrar(av)  # todos los cuadros, en orden, aunque no se muestren
                ahora = time.monotonic()
                if ahora - ultimo[0] >= 0.04:  # no saturar la ventana si el detector es rápido
                    ultimo[0] = ahora
                    self.avance.emit(ids.avance(av))

            res = procesar(self.video, self.canales, self.perfil, al_avanzar=al_avanzar, cfg=cfg)
            ids.resultados(res)
            self.terminado.emit(res)
        except _Cancelado:
            self.cancelado.emit()
        except BaseException as e:  # incluye SystemExit: en un hilo se perdería sin avisar
            self.fallo.emit(mensaje_de_error(e))