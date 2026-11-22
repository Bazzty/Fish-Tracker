"""Dónde y cómo se guardan los resultados: carpetas de outputs/ y los JSON de seguimiento y conteo.

Carpetas (lo ejecutado / modelo / secuencia):
    outputs/deteccion/<detector>/<secuencia>/                         tracker inferir
    outputs/seguimiento/<detector>_<tracker>/<secuencia>/             tracker procesar: seguimiento.json
    outputs/conteo/<detector>_<tracker>/<secuencia>/<regla>/          tracker procesar: conteo.json + formato común
    outputs/evaluacion_seguimiento/<detector>/<secuencia>/            trayectorias de cada tracker (+ metricas_*.csv/json
                                                                      en outputs/evaluacion_seguimiento/<detector>/)
<detector> es el nombre del archivo de pesos (yolo26, best) u 'oraculo'; <tracker> sale del tracker_type del YAML
(bytetrack, botsort, botsort_reid, ocsort, deepsort); <regla> es 'linea_simple' o 'dos_lineas' (histéresis).

seguimiento.json: la corrida (secuencia, modelo, tracker y sus parámetros, video) y, por canal, cada pez con
su trayectoria cuadro a cuadro (cuadro, imagen, tiempo, caja, centro, confianza).
conteo.json: la corrida, la regla de conteo usada y sus parámetros, los canales con sus líneas, cuánto contó el
sistema por canal, el conteo real (DAT-02, si la secuencia lo tiene) y el error, y cada evento de conteo.
"""
import json
from datetime import datetime
from pathlib import Path

from comun import relativa, ruta_abs
from tracker.seguimiento import tipo_y_args

REGLAS = {"linea_simple": "linea_simple", "histeresis": "dos_lineas"}
DOS_LINEAS = {"tipo": "histeresis", "min_cuadros": 5, "herencia_cuadros": 15, "herencia_distancia": 1.5}


def con_conteo(perfil: dict, regla: str | None) -> dict:
    """Copia del perfil con otra regla de conteo: 'linea_simple' o 'dos_lineas' (None = la del perfil).

    Con 'dos_lineas' se usan los parámetros del perfil si ya era de dos líneas; si no, los de variante.yaml.
    """
    if not regla or regla == nombre_regla(perfil):
        return perfil
    if regla == "linea_simple":
        return {**perfil, "conteo": {"tipo": "linea_simple"}}
    if regla == "dos_lineas":
        return {**perfil, "conteo": dict(DOS_LINEAS)}
    raise ValueError(f"Regla de conteo desconocida: '{regla}' (use linea_simple o dos_lineas).")


def nombre_detector(perfil: dict, oraculo: bool = False) -> str:
    return "oraculo" if oraculo else Path(perfil["detector"]["pesos"]).stem


def nombre_tracker(perfil: dict) -> str:
    tipo, args = tipo_y_args(perfil)
    return "botsort_reid" if tipo == "botsort" and args.get("with_reid") else tipo


def nombre_regla(perfil: dict) -> str:
    return REGLAS.get(perfil.get("conteo", {}).get("tipo", "linea_simple"), "linea_simple")


def carpeta(cfg: dict, ejecutado: str, *partes: str) -> Path:
    """outputs/<ejecutado>/<partes...> (p. ej. 'conteo', 'yolo26_botsort', 'seq_00015', 'dos_lineas')."""
    return ruta_abs(cfg["rutas"]["salidas"]).joinpath(ejecutado, *partes)


def _corrida(res, perfil: dict, secuencia: str, video: str) -> dict:
    tipo, args = tipo_y_args(perfil)
    d = perfil["detector"]
    return {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "secuencia": secuencia,
        "video": Path(video).name,
        "perfil": perfil.get("nombre"),
        "modelo": {"nombre": nombre_detector(perfil), "pesos": relativa(ruta_abs(d["pesos"])),
                   "confianza_minima": d.get("conf"), "iou_nms": d.get("iou")},
        "seguimiento": {"nombre": nombre_tracker(perfil), "tipo": tipo, "config": Path(perfil["tracker"]["config"]).as_posix(),
                        "parametros": {k: v for k, v in args.items() if k != "model"}},
        "fps": res.meta.get("fps"), "ancho": res.meta.get("ancho"), "alto": res.meta.get("alto"),
        "cuadros": res.meta.get("cuadros"),
    }


def _canales(res) -> list[dict]:
    return [{"id": c.id, "nombre": c.nombre, "caja": list(c.caja), "activo": c.activo,
             "linea_a": {"fraccion": c.linea_a, "y": round(c.y_linea(c.linea_a), 1)},
             "linea_b": {"fraccion": c.linea_b, "y": round(c.y_linea(c.linea_b), 1)}} for c in res.canales]


def escribir_seguimiento(ruta: Path, res, perfil: dict, secuencia: str, video: str, imagenes: list[str]) -> Path:
    """seguimiento.json: cada pez (canal, id) con su trayectoria. 'imagenes' = nombre del archivo de cada cuadro."""
    peces = {}
    for t in res.trayectorias:
        p = peces.setdefault((t["canal"], t["id"]), {"canal": t["canal"], "id": t["id"], "trayectoria": []})
        p["trayectoria"].append({
            "cuadro": t["cuadro"], "imagen": imagenes[t["cuadro"]] if t["cuadro"] < len(imagenes) else None,
            "tiempo_s": t["tiempo_s"],
            "caja": {"x1": t["x1"], "y1": t["y1"], "x2": t["x2"], "y2": t["y2"],
                     "ancho": round(t["x2"] - t["x1"], 1), "alto": round(t["y2"] - t["y1"], 1)},
            "centro": {"x": t["cx"], "y": t["cy"]}, "confianza": t["conf"]})
    for p in peces.values():
        p.update(primer_cuadro=p["trayectoria"][0]["cuadro"], ultimo_cuadro=p["trayectoria"][-1]["cuadro"],
                 cuadros_vistos=len(p["trayectoria"]))
    por_canal = {c.id: [p for p in peces.values() if p["canal"] == c.id] for c in res.canales if c.activo}
    doc = {"corrida": _corrida(res, perfil, secuencia, video), "canales": _canales(res),
           "resumen": {c: {"peces_seguidos": len(v)} for c, v in por_canal.items()},
           "peces_por_canal": {c: [{k: p[k] for k in ("id", "primer_cuadro", "ultimo_cuadro", "cuadros_vistos",
                                                        "trayectoria")} for p in v] for c, v in por_canal.items()}}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


def escribir_conteo(ruta: Path, res, perfil: dict, secuencia: str, video: str, imagenes: list[str],
                    referencia: dict[str, int] | None) -> Path:
    """conteo.json: la regla usada, cuánto contó el sistema, el conteo real (si hay DAT-02) y cada evento."""
    regla = perfil.get("conteo", {"tipo": "linea_simple"})
    por_canal = {}
    for c, n in res.conteos.items():
        real = referencia.get(c) if referencia is not None else None
        por_canal[c] = {"contados_por_el_sistema": n, "conteo_real": real,
                        "error": abs(n - real) if real is not None else None}
    total = sum(res.conteos.values())
    total_real = sum(referencia.values()) if referencia is not None else None
    doc = {
        "corrida": _corrida(res, perfil, secuencia, video),
        "regla_de_conteo": {"nombre": nombre_regla(perfil), "tipo": regla.get("tipo", "linea_simple"),
                            "parametros": {k: v for k, v in regla.items() if k != "tipo"}},
        "conteo_real": ("DAT-02: línea simple aplicada a las trayectorias etiquetadas, con los mismos canales"
                        if referencia is not None else "no disponible: la secuencia no tiene gt.txt en DAT-02"),
        "canales": _canales(res),
        "resultado": {"por_canal": por_canal,
                      "total": {"contados_por_el_sistema": total, "conteo_real": total_real,
                                "error": abs(total - total_real) if total_real is not None else None}},
        "eventos": [{**e, "imagen": imagenes[e["cuadro"]] if e["cuadro"] < len(imagenes) else None} for e in res.eventos],
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta
