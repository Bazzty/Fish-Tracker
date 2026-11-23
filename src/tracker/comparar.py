"""Error de conteo de varias configuraciones sobre las mismas secuencias (T19: base vs. variante).

Lee los metricas_<grupo>.json de `tracker evaluar-seguimiento` y arma una tabla Markdown con el conteo de cada
configuración por secuencia, su error y tres totales:
    error neto       |suma conteo - suma referencia|: lo que se equivoca el total (los errores pueden cancelarse).
    error absoluto   suma de |conteo - referencia| por secuencia: no deja que un exceso tape una falta.
    error relativo   error absoluto / suma de la referencia.

Cada entrada es ETIQUETA=RUTA.json o ETIQUETA=RUTA.json:TRACKER (el nombre del YAML sin extensión), cuando el JSON
trae más de un tracker. Las configuraciones deben cubrir las mismas secuencias y la misma referencia.

Uso:
    uv run tracker comparar "Base=outputs/.../best/metricas_test_linea_simple.json" \\
        "Variante=resultados/seguimiento_test_variante.json" --salida resultados/tablas/error_conteo_test.md
"""
import json
from pathlib import Path


def leer(entrada: str) -> tuple[str, dict]:
    """'Etiqueta=ruta.json[:tracker]' -> (etiqueta, {'meta': ..., 'total': ..., 'por_secuencia': ...})."""
    etiqueta, sep, resto = entrada.partition("=")
    if not sep or not etiqueta or not resto:
        raise ValueError(f"Entrada '{entrada}': use ETIQUETA=RUTA.json o ETIQUETA=RUTA.json:TRACKER")
    ruta, tracker = resto, None
    if not Path(ruta).exists() and ":" in resto:
        ruta, tracker = resto.rsplit(":", 1)
    if not Path(ruta).exists():
        raise FileNotFoundError(f"No existe {ruta}")
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    trackers = d.get("trackers", {})
    if tracker is None:
        if len(trackers) != 1:
            raise ValueError(f"{ruta} trae {len(trackers)} trackers ({', '.join(trackers)}): indique ':TRACKER'")
        tracker = next(iter(trackers))
    if tracker not in trackers:
        raise ValueError(f"{ruta} no trae el tracker '{tracker}' (hay: {', '.join(trackers)})")
    t = trackers[tracker]  # una configuración puede traer sus propios pesos y regla
    meta = dict(ruta=Path(ruta).as_posix(), pesos=t.get("pesos", d.get("pesos")), tracker=t.get("tracker", tracker),
                regla=t.get("regla_conteo", d.get("regla_conteo")))
    return etiqueta, dict(meta=meta, total=t["total"], por_secuencia=t["por_secuencia"])


def resumen(conf: dict) -> dict:
    seqs = conf["por_secuencia"].values()
    conteo = sum(s["conteo_tracker"] for s in seqs)
    ref = sum(s["conteo_referencia"] for s in seqs)
    absoluto = sum(abs(s["conteo_tracker"] - s["conteo_referencia"]) for s in seqs)
    exactas = sum(s["conteo_tracker"] == s["conteo_referencia"] for s in seqs)
    return dict(conteo=conteo, referencia=ref, neto=abs(conteo - ref), absoluto=absoluto,
                relativo=absoluto / ref if ref else 0.0, exactas=exactas,
                IDF1=conf["total"].get("IDF1"), IDSW=conf["total"].get("IDSW"))


def comprobar(confs: dict[str, dict]) -> list[str]:
    """Mismas secuencias y misma referencia en todas las configuraciones."""
    (e0, c0), *resto = confs.items()
    s0 = set(c0["por_secuencia"])
    for e, c in resto:
        if set(c["por_secuencia"]) != s0:
            raise ValueError(f"'{e}' y '{e0}' no cubren las mismas secuencias")
        for s in s0:
            if c["por_secuencia"][s]["conteo_referencia"] != c0["por_secuencia"][s]["conteo_referencia"]:
                raise ValueError(f"'{e}' y '{e0}' tienen distinta referencia en {s}")
    return sorted(s0)


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f} %".replace(".", ",")


def tabla(confs: dict[str, dict]) -> str:
    seqs = comprobar(confs)
    etiquetas = list(confs)
    ref = {s: next(iter(confs.values()))["por_secuencia"][s]["conteo_referencia"] for s in seqs}
    lineas = ["## Configuraciones", "", "| Configuración | Pesos | Tracker | Regla de conteo | JSON |",
              "|---|---|---|---|---|"]
    for e, c in confs.items():
        m = c["meta"]
        lineas.append(f"| {e} | `{m['pesos']}` | {m['tracker']} | {m['regla']} | `{m['ruta']}` |")
    lineas += ["", "## Total", "", "| | " + " | ".join(etiquetas) + " |", "|---" * (len(etiquetas) + 1) + "|"]
    res = {e: resumen(c) for e, c in confs.items()}
    filas = [
        ("Conteo / referencia", lambda r: f"{r['conteo']} / {r['referencia']}"),
        ("Error neto", lambda r: str(r["neto"])),
        ("Error absoluto (suma por secuencia)", lambda r: str(r["absoluto"])),
        ("Error relativo", lambda r: _pct(r["relativo"])),
        ("Secuencias con conteo exacto", lambda r: f"{r['exactas']} / {len(seqs)}"),
        ("IDF1", lambda r: _pct(r["IDF1"])),
        ("Cambios de ID", lambda r: "—" if r["IDSW"] is None else str(r["IDSW"])),
    ]
    if all(r["IDF1"] is None for r in res.values()):  # sin DAT-02 en la corrida no hay métricas de seguimiento
        filas = filas[:-2]
    lineas += [f"| {n} | " + " | ".join(f(res[e]) for e in etiquetas) + " |" for n, f in filas]
    lineas += ["", "## Por secuencia (conteo; entre paréntesis, el error con signo)", "",
               "| Secuencia | Referencia | " + " | ".join(etiquetas) + " |", "|---" * (len(etiquetas) + 2) + "|"]
    for s in seqs:
        celdas = []
        for e in etiquetas:
            n = confs[e]["por_secuencia"][s]["conteo_tracker"]
            celdas.append(f"{n} ({n - ref[s]:+d})" if n != ref[s] else str(n))
        lineas.append(f"| {s} | {ref[s]} | " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


def comparar(entradas: list[str], salida: str | Path | None = None, titulo: str | None = None) -> str:
    if len(entradas) < 2:
        raise ValueError("Se necesitan al menos dos configuraciones para comparar")
    confs = dict(leer(x) for x in entradas)
    if len(confs) != len(entradas):
        raise ValueError("Las etiquetas deben ser distintas")
    md = f"# {titulo or 'Error de conteo: ' + ' vs. '.join(confs)}\n\n" + tabla(confs)
    if salida:
        Path(salida).parent.mkdir(parents=True, exist_ok=True)
        Path(salida).write_text(md, encoding="utf-8")
    return md
