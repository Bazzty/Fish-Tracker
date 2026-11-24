from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from .canal_libre import CanalLibre
from .diagnostico import diagnosticar

FORMATO = "tracker-resultados"
VERSION = 1


def nombre_secuencia(video: str) -> str:
    """seq_0005_prueba.mp4 -> seq_0005; si el nombre no trae «seq_NNNN», el nombre del archivo sin extensión."""
    stem = Path(video).stem
    m = re.search(r"seq_\d+", stem)
    return m.group(0) if m else stem


def _r(v, n=1):
    return round(float(v), n)


def construir_documento(res, perfil: dict | None = None) -> dict:
    """`res` es un tracker.pipeline.Resultados; `perfil`, el contenido del YAML del perfil usado (opcional)."""
    meta = res.meta
    fps = float(meta.get("fps") or 0) or 10.0
    activos = [c for c in res.canales if c.activo]

    dets, tray, evs = defaultdict(list), defaultdict(list), defaultdict(list)
    for d in res.detecciones:
        dets[d["cuadro"]].append({"canal": d["canal"], "x1": _r(d["x1"]), "y1": _r(d["y1"]), "x2": _r(d["x2"]),
                                  "y2": _r(d["y2"]), "conf": _r(d["conf"], 3)})
    for t in res.trayectorias:
        tray[t["cuadro"]].append({"canal": t["canal"], "id": int(t["id"]), "x1": _r(t["x1"]), "y1": _r(t["y1"]),
                                  "x2": _r(t["x2"]), "y2": _r(t["y2"]), "conf": _r(t["conf"], 3),
                                  "cx": _r(t["cx"]), "cy": _r(t["cy"])})
    for e in res.eventos:
        evs[e["cuadro"]].append({"canal": e["canal"], "id": int(e["id"]), "conteo": int(e["conteo"])})
    frames = set(dets) | set(tray) | set(evs)
    total_cuadros = int(meta.get("cuadros") or 0) or ((max(frames) + 1) if frames else 0)

    corriente = {c.id: 0 for c in activos}
    cuadros = []
    for f in range(total_cuadros):
        for e in evs.get(f, []):
            corriente[e["canal"]] = e["conteo"]
        cuadros.append({"cuadro": f, "tiempo_s": round(f / fps, 4), "detecciones": dets.get(f, []),
                        "trayectorias": tray.get(f, []), "eventos": evs.get(f, []), "conteos": dict(corriente)})

    diag = diagnosticar(res)
    contado = {(e["canal"], int(e["id"])): e["cuadro"] for e in res.eventos}
    ids_por_canal = defaultdict(set)
    for t in res.trayectorias:
        ids_por_canal[t["canal"]].add(int(t["id"]))

    canales = []
    for c in res.canales:
        lc = CanalLibre.desde_canal(c)
        canales.append({
            "id": lc.id, "nombre": lc.nombre, "activo": lc.activo, "forma": lc.forma,
            "caja": [_r(v) for v in lc.caja], "puntos": [[_r(x), _r(y)] for x, y in lc.puntos],
            "linea_a": round(lc.linea_a, 4), "linea_b": round(lc.linea_b, 4),
            "linea_a_y": _r(lc.y_linea(lc.linea_a)), "linea_b_y": _r(lc.y_linea(lc.linea_b)),
            "conteo": int(res.conteos.get(lc.id, 0)) if lc.activo else None,
            "ids_distintos": len(ids_por_canal.get(lc.id, ())),
        })

    por_canal = {c.id: int(res.conteos.get(c.id, 0)) for c in activos}
    trayectorias = [{
        "canal": x.canal, "id": x.id, "cuadro_inicio": x.ini, "cuadro_fin": x.fin, "cuadros_vistos": x.n,
        "alto_inicio_pct": _r(x.rel_ini * 100), "alto_fin_pct": _r(x.rel_fin * 100), "sentido": x.sentido,
        "contado": (x.canal, x.id) in contado, "cuadro_conteo": contado.get((x.canal, x.id)),
    } for x in diag.pistas]

    pesos = meta.get("pesos")
    return {
        "formato": FORMATO,
        "version": VERSION,
        "secuencia": {
            "nombre": nombre_secuencia(meta.get("video", "")), "video": meta.get("video"),
            "ancho": meta.get("ancho"), "alto": meta.get("alto"), "fps": fps, "cuadros": total_cuadros,
            "duracion_s": round(total_cuadros / fps, 3),
        },
        "procesamiento": {
            "fecha": meta.get("fecha"), "perfil": meta.get("perfil"),
            "modelo": Path(pesos).stem.upper() if pesos else None, "pesos": pesos,
            "dispositivo": meta.get("dispositivo"), "duracion_proceso_s": meta.get("procesamiento_s"),
            "solo_detectar": bool(meta.get("solo_detectar", False)), "configuracion_perfil": perfil,
            "notas": [meta["nota_ids"]] if meta.get("nota_ids") else [],
        },
        "canales": canales,
        "conteo": {
            "total": sum(por_canal.values()), "por_canal": por_canal,
            "regla": (perfil or {}).get("conteo"),
            "eventos": [{"canal": e["canal"], "id": int(e["id"]), "cuadro": e["cuadro"],
                         "tiempo_s": _r(e["tiempo_s"], 4), "conteo": int(e["conteo"])} for e in res.eventos],
        },
        "resumen": {
            "total_peces": sum(por_canal.values()), "por_canal": por_canal,
            "ids_distintos": sum(len(v) for v in ids_por_canal.values()), "cuadros": total_cuadros,
            "detecciones": len(res.detecciones), "cuadros_con_detecciones": len(dets),
            "trayectorias": len(diag.pistas),
        },
        "trayectorias_resumen": trayectorias,
        "diagnostico": {
            "descripcion": "Heurística sobre las trayectorias (sin etiquetas de referencia).",
            "resumen_por_canal": diag.resumen, "fragmentaciones_probables": diag.fragmentaciones,
            "trayectorias_cortas": diag.cortas, "parametros": asdict(diag.params),
            "fallos": [asdict(f) for f in diag.fallos],
        },
        "cuadros": cuadros,
    }


def guardar_json(ruta, doc: dict) -> None:
    """Escribe el JSON legible: el encabezado con sangría y cada cuadro en una sola línea."""
    cuadros = doc["cuadros"]
    cabecera = json.dumps({k: v for k, v in doc.items() if k != "cuadros"}, ensure_ascii=False, indent=2, default=str)
    filas = ",\n".join("    " + json.dumps(c, ensure_ascii=False, separators=(",", ":")) for c in cuadros)
    texto = cabecera.rstrip()[:-1].rstrip() + ',\n  "cuadros": [\n' + filas + "\n  ]\n}\n"
    Path(ruta).write_text(texto, encoding="utf-8")


def leer_json(ruta):
    """Reconstruye un tracker.pipeline.Resultados desde el JSON (lanza ValueError si no es válido)."""
    from tracker.pipeline import Resultados

    try:
        doc = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"No se pudo leer el archivo: {e}") from e
    if not isinstance(doc, dict) or doc.get("formato") != FORMATO:
        raise ValueError("El archivo no es un resultado del Tracker (falta «formato»: tracker-resultados).")
    if doc.get("version") != VERSION:
        raise ValueError(f"Versión de resultados no soportada: {doc.get('version')}")
    try:
        seq, proc = doc["secuencia"], doc["procesamiento"]
        canales = [CanalLibre(id=c["id"], caja=c["caja"], nombre=c["nombre"], linea_a=c["linea_a"],
                              linea_b=c["linea_b"], activo=c["activo"],
                              puntos=tuple(tuple(p) for p in c["puntos"])) for c in doc["canales"]]
        detecciones, trayectorias = [], []
        for f in doc["cuadros"]:
            base = {"cuadro": f["cuadro"], "tiempo_s": f["tiempo_s"]}
            detecciones += [{**base, **d} for d in f["detecciones"]]
            trayectorias += [{**base, **t} for t in f["trayectorias"]]
        eventos = [dict(e) for e in doc["conteo"]["eventos"]]
        por_canal = dict(doc["conteo"]["por_canal"])
        meta = {"video": seq["video"], "secuencia": seq["nombre"], "perfil": proc["perfil"], "pesos": proc["pesos"],
                "fps": seq["fps"], "ancho": seq["ancho"], "alto": seq["alto"], "cuadros": seq["cuadros"],
                "solo_detectar": proc["solo_detectar"], "dispositivo": proc.get("dispositivo"),
                "conteos": por_canal, "total": doc["conteo"]["total"]}
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"El archivo de resultados está incompleto o dañado: {e}") from e
    return Resultados(meta=meta, canales=canales, detecciones=detecciones, trayectorias=trayectorias,
                      eventos=eventos, conteos=por_canal)
