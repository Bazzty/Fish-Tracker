"""Diagnóstico del seguimiento (T11): clasifica fallos a partir de trayectorias.csv.

Sin etiquetas de referencia no se puede saber con certeza qué es un fallo, así que esto es una
HEURÍSTICA sobre las trayectorias exportadas (formato común). Los peces avanzan de arriba hacia
abajo dentro del tubo; se espera que cada ID nazca arriba y termine abajo.

  caja intermitente: un ID desaparece unos cuadros y reaparece (la detección parpadea).
  ID perdido:        un ID termina en medio del tubo, sin llegar a la salida (ni al final del video).
  ID nuevo:          un ID aparece en medio del tubo, sin haber entrado por arriba (ni al inicio del video).

Un ID perdido seguido de un ID nuevo cercano en tiempo y posición es una fragmentación probable:
el mismo pez con dos IDs (riesgo de contarlo dos veces).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot

TIPOS = ("caja_intermitente", "id_perdido", "id_nuevo")
ETIQUETAS = {"caja_intermitente": "Caja intermitente", "id_perdido": "ID perdido", "id_nuevo": "ID nuevo"}


@dataclass
class Params:
    min_cuadros: int = 5  # trayectorias más cortas no se juzgan como perdido/nuevo (falsos positivos)
    borde: float = 0.10  # fracción del alto del tubo que cuenta como entrada (arriba) y salida (abajo)
    margen_cuadros: int = 5  # tolerancia cerca del inicio y del final del video
    ventana: int = 30  # cuadros máximos entre un ID perdido y un ID nuevo para enlazarlos
    dist_rel: float = 1.5  # distancia máxima del enlace, en tamaños de caja


@dataclass
class Fallo:
    tipo: str
    canal: str
    id: int
    cuadro: int
    tiempo_s: float
    detalle: str
    enlace: int | None = None  # ID con el que probablemente se fragmentó


@dataclass
class Pista:
    """Resumen de una trayectoria (canal, id)."""
    canal: str
    id: int
    ini: int  # primer cuadro
    fin: int  # último cuadro
    n: int  # cuadros en que se vio
    rel_ini: float  # posición inicial, fracción del alto del tubo desde arriba
    rel_fin: float
    sentido: str  # "baja" | "sube" | "quieto"
    cruza_a: bool  # ¿cumple la regla de la línea base? (visto sobre A y luego en A o más abajo)


@dataclass
class GuiaLinea:
    """Ayuda para ubicar la línea A de un tubo, según dónde nacen y terminan sus trayectorias."""
    canal: str
    n: int  # trayectorias
    cruzan: int  # las que cruzan la línea A
    linea_a: float
    p_ini: float | None  # el 75 % de las trayectorias largas nace más arriba que esto
    p_fin: float | None  # el 75 % de las trayectorias largas termina más abajo que esto
    sugerida: tuple[float, float] | None  # rango donde conviene la línea A


@dataclass
class Diagnostico:
    fallos: list[Fallo]
    resumen: dict[str, dict[str, int]]  # canal -> {"ids", *TIPOS, "fragmentaciones"}
    cortas: int
    fragmentaciones: int
    params: Params
    hay_trayectorias: bool
    pistas: list[Pista] = field(default_factory=list)
    guias: dict[str, GuiaLinea] = field(default_factory=dict)


def _percentil(valores: list[float], q: float) -> float:
    v = sorted(valores)
    return v[min(len(v) - 1, max(0, round(q * (len(v) - 1))))]


def diagnosticar(res, params: Params | None = None) -> Diagnostico:
    """'res' es un tracker.pipeline.Resultados (por ejemplo, leído con tracker.formato.leer)."""
    p = params or Params()
    filas = res.trayectorias
    if not filas:
        return Diagnostico([], {}, 0, 0, p, False)

    cajas = {c.id: c.caja for c in res.canales}
    lineas = {c.id: c.linea_a for c in res.canales}
    fps = float(res.meta.get("fps") or 0) or 10.0
    total = int(res.meta.get("cuadros") or 0) or (max(f["cuadro"] for f in filas) + 1)

    por_id: dict[tuple[str, int], dict[int, dict]] = {}
    for f in filas:
        por_id.setdefault((f["canal"], f["id"]), {})[f["cuadro"]] = f

    fallos: list[Fallo] = []
    resumen: dict[str, dict[str, int]] = {
        c.id: {"ids": 0, **{t: 0 for t in TIPOS}, "fragmentaciones": 0} for c in res.canales if c.activo
    }  # todos los tubos activos, también los que no tuvieron peces
    pistas: list[Pista] = []
    perdidos: list[tuple[Fallo, float, float, float]] = []  # fallo, cx, cy, tamaño de caja
    nuevos: list[tuple[Fallo, float, float]] = []
    cortas = 0

    def nuevo_fallo(tipo, canal, tid, cuadro, detalle):
        f = Fallo(tipo, canal, tid, cuadro, round(cuadro / fps, 2), detalle)
        fallos.append(f)
        resumen[canal][tipo] += 1
        return f

    for (canal, tid), frames in sorted(por_id.items()):
        r = resumen.setdefault(canal, {"ids": 0, **{t: 0 for t in TIPOS}, "fragmentaciones": 0})
        r["ids"] += 1
        fs = sorted(frames)

        for a, b in zip(fs, fs[1:]):  # huecos dentro de la trayectoria
            if b - a > 1:
                n = b - a - 1
                nuevo_fallo("caja_intermitente", canal, tid, a + 1,
                            f"faltó {n} cuadro(s) ({a + 1}-{b - 1}) y reapareció con el mismo ID")

        caja = cajas.get(canal)
        if caja is not None:
            y1, alto = caja[1], caja[3] - caja[1]
            ini, fin = frames[fs[0]], frames[fs[-1]]
            rel_ini, rel_fin = (ini["cy"] - y1) / alto, (fin["cy"] - y1) / alto
            ya = y1 + lineas[canal] * alto
            cruza = any(frames[a]["cy"] < ya <= frames[b]["cy"] for a, b in zip(fs, fs[1:]))
            d = rel_fin - rel_ini
            pistas.append(Pista(canal, tid, fs[0], fs[-1], len(fs), rel_ini, rel_fin,
                                "baja" if d > 0.05 else "sube" if d < -0.05 else "quieto", cruza))
        if len(fs) < p.min_cuadros:
            cortas += 1
            continue
        if caja is None:
            continue

        if fs[-1] < total - 1 - p.margen_cuadros and rel_fin < 1 - p.borde:
            f = nuevo_fallo("id_perdido", canal, tid, fs[-1],
                            f"terminó en el cuadro {fs[-1]} a {rel_fin:.0%} del alto del tubo")
            tam = max(fin["x2"] - fin["x1"], fin["y2"] - fin["y1"])
            perdidos.append((f, fin["cx"], fin["cy"], tam))
        if fs[0] > p.margen_cuadros and rel_ini > p.borde:
            f = nuevo_fallo("id_nuevo", canal, tid, fs[0],
                            f"apareció en el cuadro {fs[0]} a {rel_ini:.0%} del alto del tubo")
            nuevos.append((f, ini["cx"], ini["cy"]))

    # enlaces: ID perdido -> ID nuevo cercano en tiempo y espacio (cada ID se usa una sola vez)
    cand = []
    for ia, (fa, ax, ay, tam) in enumerate(perdidos):
        for ib, (fb, bx, by) in enumerate(nuevos):
            dt = fb.cuadro - fa.cuadro
            d = hypot(bx - ax, by - ay)
            if fa.canal == fb.canal and 0 < dt <= p.ventana and d <= p.dist_rel * tam:
                cand.append((d, dt, ia, ib))
    usados_a, usados_b = set(), set()
    fragmentaciones = 0
    for d, dt, ia, ib in sorted(cand):
        if ia in usados_a or ib in usados_b:
            continue
        usados_a.add(ia)
        usados_b.add(ib)
        fa, fb = perdidos[ia][0], nuevos[ib][0]
        fa.enlace, fb.enlace = fb.id, fa.id
        fa.detalle += f"; probable mismo pez que el ID {fb.id}"
        fb.detalle += f"; probable mismo pez que el ID {fa.id}"
        resumen[fa.canal]["fragmentaciones"] += 1
        fragmentaciones += 1

    fallos.sort(key=lambda f: (f.cuadro, f.canal, f.id))

    guias: dict[str, GuiaLinea] = {}
    for c in res.canales:
        propias = [x for x in pistas if x.canal == c.id]
        largas = [x for x in propias if x.n >= p.min_cuadros]
        p_ini = _percentil([x.rel_ini for x in largas], 0.75) if largas else None
        p_fin = _percentil([x.rel_fin for x in largas], 0.25) if largas else None
        sugerida = (p_ini, p_fin) if (p_ini is not None and p_fin is not None and p_ini < p_fin) else None
        guias[c.id] = GuiaLinea(c.id, len(propias), sum(x.cruza_a for x in propias), c.linea_a, p_ini, p_fin, sugerida)
    pistas.sort(key=lambda x: (x.canal, x.id))
    return Diagnostico(fallos, resumen, cortas, fragmentaciones, p, True, pistas, guias)
