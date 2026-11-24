from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tracker.canales import VERSION, Canal, guardar_canales

TOL = 0.5  # px: por debajo de esto, un lado se considera recto


def bbox(pts) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def punto_en_poligono(x: float, y: float, pts) -> bool:
    dentro = False
    n = len(pts)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _se_cruzan(p1, p2, p3, p4) -> bool:
    return _orient(p3, p4, p1) * _orient(p3, p4, p2) < 0 and _orient(p1, p2, p3) * _orient(p1, p2, p4) < 0


def es_simple(pts) -> bool:
    """El cuadrilátero no se cruza consigo mismo (no es un «moño»)."""
    return not (_se_cruzan(pts[0], pts[1], pts[2], pts[3]) or _se_cruzan(pts[1], pts[2], pts[3], pts[0]))


def cuerda(pts, y: float) -> tuple[float, float] | None:
    """Extremos (x_izq, x_der) de la línea horizontal `y` dentro del polígono, o None si no lo corta."""
    xs = []
    for i in range(len(pts)):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % len(pts)]
        if y1 != y2 and (y1 - y) * (y2 - y) <= 0:
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


def recortar_franja(pts, y0: float, y1: float) -> list[tuple[float, float]]:
    """Parte del polígono entre las alturas y0 e y1 (la zona de conteo entre las líneas A y B)."""

    def recorta(poly, dentro, y):
        out = []
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            if dentro(a):
                out.append(a)
            if dentro(a) != dentro(b):
                out.append((a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]), y))
        return out

    poly = recorta(list(pts), lambda p: p[1] >= y0, y0)
    return recorta(poly, lambda p: p[1] <= y1, y1) if poly else []


@dataclass
class CanalLibre(Canal):
    puntos: tuple = ()  # 4 esquinas: arriba-izq, arriba-der, abajo-der, abajo-izq

    def __post_init__(self):
        if self.puntos:
            self.puntos = tuple((float(x), float(y)) for x, y in self.puntos)
            if len(self.puntos) != 4:
                raise ValueError(f"{self.id}: un tubo libre necesita exactamente 4 esquinas")
            self.caja = bbox(self.puntos)
        super().__post_init__()  # valida caja y líneas
        if not self.puntos:
            x1, y1, x2, y2 = self.caja
            self.puntos = ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
        self._actualizar_forma()

    # ---- forma ----
    def es_rectangular(self) -> bool:
        (ax, ay), (bx, by), (cx, cy), (dx, dy) = self.puntos
        return abs(ax - dx) < TOL and abs(bx - cx) < TOL and abs(ay - by) < TOL and abs(dy - cy) < TOL

    def _actualizar_forma(self) -> None:
        self.forma = "rect" if self.es_rectangular() else "cuadrilatero"

    def set_puntos(self, pts) -> None:
        self.puntos = tuple((float(x), float(y)) for x, y in pts)
        self.caja = bbox(self.puntos)
        self._actualizar_forma()

    def set_caja(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """Mueve y escala el tubo para que su caja envolvente sea esta (conserva la forma)."""
        ox1, oy1, ox2, oy2 = self.caja
        sx, sy = (x2 - x1) / (ox2 - ox1), (y2 - y1) / (oy2 - oy1)
        self.set_puntos([(x1 + (x - ox1) * sx, y1 + (y - oy1) * sy) for x, y in self.puntos])

    def contiene(self, cx: float, cy: float) -> bool:
        if self.es_rectangular():
            x1, y1, x2, y2 = self.caja
            return x1 <= cx <= x2 and y1 <= cy <= y2
        return punto_en_poligono(cx, cy, self.puntos)

    # ---- conversiones ----
    @classmethod
    def desde_canal(cls, c: Canal) -> "CanalLibre":
        if isinstance(c, CanalLibre):
            return c
        return cls(c.id, c.caja, c.nombre, c.linea_a, c.linea_b, c.activo)

    def a_canal(self) -> Canal:
        """Canal rectangular con la caja envolvente (lo único que entiende el formato común)."""
        return Canal(self.id, self.caja, self.nombre, self.linea_a, self.linea_b, self.activo, "rect")

    def a_dict(self) -> dict:
        d = {"id": self.id, "caja": list(self.caja), "nombre": self.nombre, "linea_a": self.linea_a,
             "linea_b": self.linea_b, "activo": self.activo, "forma": self.forma}
        if self.forma != "rect":
            d["puntos"] = [list(p) for p in self.puntos]
        return d


def guardar_canales_libres(ruta, canales, video=None, ancho=None, alto=None) -> None:
    """Si todos los tubos son rectángulos escribe EXACTAMENTE el JSON del formato común."""
    canales = [CanalLibre.desde_canal(c) for c in canales]
    if all(c.es_rectangular() for c in canales):
        guardar_canales(ruta, [c.a_canal() for c in canales], video, ancho, alto)
        return
    ids = [c.id for c in canales]
    if len(set(ids)) != len(ids):
        raise ValueError("Hay ids de canal repetidos.")
    doc = {"version": VERSION, "video": {"archivo": video, "ancho": ancho, "alto": alto},
           "canales": [c.a_dict() for c in canales]}
    Path(ruta).write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")


def cargar_canales_libres(ruta) -> list[CanalLibre]:
    doc = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if doc.get("version") != VERSION:
        raise ValueError(f"Versión de canales no soportada: {doc.get('version')}")
    out = []
    for c in doc["canales"]:
        pts = tuple(tuple(p) for p in c["puntos"]) if c.get("puntos") else ()
        out.append(CanalLibre(id=c["id"], caja=c["caja"], nombre=c.get("nombre", ""),
                              linea_a=c.get("linea_a", 0.40), linea_b=c.get("linea_b", 0.60),
                              activo=c.get("activo", True), puntos=pts))
    return out
