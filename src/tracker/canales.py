"""Canal (tubo) y su zona de conteo. Se guardan en JSON y los usan la GUI, el conteo y la exportación.

Un canal es un rectángulo en píxeles del video. La zona de conteo son dos líneas horizontales
dentro del canal, dadas como fracción de su alto medida desde arriba (0 = borde superior):
    A (entrada) < B (salida). Los peces avanzan de arriba hacia abajo, igual que en el Lab 15.
El campo 'forma' queda para extender a polígono sin romper los archivos ya guardados.
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

VERSION = 1


@dataclass
class Canal:
    id: str                     # estable y único, p. ej. "canal_1"; es la clave en todos los archivos
    caja: tuple[float, float, float, float]   # x1, y1, x2, y2 en píxeles del video
    nombre: str = ""            # etiqueta para mostrar en la interfaz
    linea_a: float = 0.40       # fracción del alto del canal
    linea_b: float = 0.60
    activo: bool = True         # False: se marcó pero no se analiza
    forma: str = "rect"

    def __post_init__(self):
        self.caja = tuple(float(v) for v in self.caja)
        x1, y1, x2, y2 = self.caja
        if not (x1 < x2 and y1 < y2):
            raise ValueError(f"{self.id}: la caja debe cumplir x1<x2 e y1<y2, recibido {self.caja}")
        if not (0.0 <= self.linea_a < self.linea_b <= 1.0):
            raise ValueError(f"{self.id}: se exige 0 <= linea_a < linea_b <= 1")

    def contiene(self, cx: float, cy: float) -> bool:
        x1, y1, x2, y2 = self.caja
        return x1 <= cx <= x2 and y1 <= cy <= y2

    def y_linea(self, fraccion: float) -> float:
        """Coordenada y (en píxeles del video) de una fracción del alto del canal."""
        _, y1, _, y2 = self.caja
        return y1 + fraccion * (y2 - y1)


def canal_de(canales: list[Canal], cx: float, cy: float) -> Canal | None:
    """Canal activo que contiene el punto. Si dos se solapan, gana el primero de la lista."""
    return next((c for c in canales if c.activo and c.contiene(cx, cy)), None)


def guardar_canales(ruta: str | Path, canales: list[Canal], video: str | None = None,
                    ancho: int | None = None, alto: int | None = None) -> None:
    ids = [c.id for c in canales]
    if len(set(ids)) != len(ids):
        raise ValueError("Hay ids de canal repetidos.")
    doc = {"version": VERSION, "video": {"archivo": video, "ancho": ancho, "alto": alto},
           "canales": [asdict(c) for c in canales]}
    Path(ruta).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def ruta_canales(nombre: str | Path) -> Path:
    """Una ruta a un JSON, o su nombre en configs/: 'dos_tubos' -> configs/canales_dos_tubos.json."""
    from comun import ruta_abs

    n = str(nombre)
    candidatos = [Path(n), ruta_abs(n), ruta_abs("configs") / n, ruta_abs("configs") / f"{n}.json",
                  ruta_abs("configs") / f"canales_{n}.json"]
    for c in candidatos:
        if c.is_file():
            return c
    raise FileNotFoundError(f"No existe el JSON de canales '{n}' (ni como ruta ni en configs/).")


def cargar_canales(ruta: str | Path) -> list[Canal]:
    doc = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if doc.get("version") != VERSION:
        raise ValueError(f"Versión de canales no soportada: {doc.get('version')}")
    return [Canal(**c) for c in doc["canales"]]
