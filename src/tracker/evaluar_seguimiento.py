"""Evaluación del seguimiento contra las trayectorias etiquetadas (DAT-02): IDF1, ID switches y MOTA.

Entrada: imágenes de data/<seq>/images y DAT-02 en data/tracking/<seq>[_Final]/gt/gt.txt (formato MOT),
con frames.txt (cuadro,imagen) para unir cada cuadro del gt con su imagen.
Salida en outputs/evaluacion_seguimiento/<perfil>/:
    metricas.csv     una fila por secuencia y tracker, y una fila TOTAL por tracker (ordenadas por IDF1).
                     Columnas: PERCENTAGE OF CORRECT IDs (IDF1), TIMES ID CHANGED (IDSW), MOTA,
                     EXTRA BOXES (FP), MISSING BOXES (FN), Frag, MT, ML, TOTAL FISHES (peces del GT)
                     y FISHES COUNTED BY TRACKER (IDs distintos que creó el tracker).
    trayectorias/    <tracker>/<seq>.txt en formato MOT; los dibuja scripts/video_seguimiento.py.

El detector corre una vez por secuencia y cada tracker usa esas mismas detecciones, con un solo canal
del tamaño del cuadro. Con --oraculo las detecciones son las cajas del GT (aísla el tracker).
Una predicción es el mismo pez del GT si su IoU >= 0,5 (MOTChallenge).

Uso:
    uv run tracker evaluar-seguimiento --conjunto val
    uv run tracker evaluar-seguimiento --seq seq_00015 --trackers configs/bytetrack.yaml configs/botsort.yaml
    uv run tracker evaluar-seguimiento --conjunto val --oraculo
"""
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from comun import dir_datos, leer_yaml, listar_cuadros, ruta_abs
from tracker.canales import Canal

VACIO = np.zeros((0, 5))


def dir_gt(cfg: dict, seq: str) -> Path:
    base = ruta_abs(cfg["rutas"]["tracking"])
    return base / seq if (base / seq).is_dir() else base / f"{seq}_Final"


def con_gt(cfg: dict) -> list[str]:
    base = ruta_abs(cfg["rutas"]["tracking"])
    if not base.is_dir():
        return []
    return sorted(p.name.removesuffix("_Final") for p in base.iterdir() if (p / "gt" / "gt.txt").exists())


def leer_mot(ruta: Path) -> dict[int, np.ndarray]:
    """{cuadro: [[id, x, y, w, h], ...]}. Las filas con conf 0 no cuentan (MOTChallenge)."""
    d = defaultdict(list)
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        v = [float(x) for x in linea.split(",") if x.strip()]
        if len(v) >= 6 and (len(v) < 7 or v[6] != 0):
            d[int(v[0])].append(v[1:6])
    return {f: np.array(a) for f, a in d.items()}


def cuadros_seq(cfg: dict, seq: str) -> list[tuple[int, Path]]:
    """(cuadro del gt, imagen). Sin frames.txt, el cuadro 1 es la primera imagen."""
    imgs = dir_datos(cfg) / seq / "images"
    frames = dir_gt(cfg, seq) / "frames.txt"
    if frames.exists():
        pares = [l.split(",", 1) for l in frames.read_text(encoding="utf-8").splitlines() if "," in l]
        return [(int(f), imgs / n.strip()) for f, n in pares]
    return [(i + 1, r) for i, (_, r) in enumerate(listar_cuadros(imgs))]


def iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU entre cajas x, y, w, h (a: N, b: M)."""
    ix = np.clip(np.minimum(a[:, None, 0] + a[:, None, 2], b[None, :, 0] + b[None, :, 2])
                 - np.maximum(a[:, None, 0], b[None, :, 0]), 0, None)
    iy = np.clip(np.minimum(a[:, None, 1] + a[:, None, 3], b[None, :, 1] + b[None, :, 3])
                 - np.maximum(a[:, None, 1], b[None, :, 1]), 0, None)
    inter = ix * iy
    return inter / ((a[:, 2] * a[:, 3])[:, None] + (b[:, 2] * b[:, 3])[None] - inter + 1e-9)


def acumular(gt: dict, pred: dict, cuadros: list[int], umbral: float = 0.5) -> dict:
    """Conteos de una secuencia (CLEAR-MOT e identidad). Se suman entre secuencias."""
    c = defaultdict(float)
    mapa, vivo, seguido, previo, co, vistos = {}, defaultdict(int), defaultdict(int), {}, defaultdict(int), set()
    for f in cuadros:
        g, p = gt.get(f, VACIO), pred.get(f, VACIO)
        gi, pi = g[:, 0].astype(int).tolist(), p[:, 0].astype(int).tolist()
        m = iou(g[:, 1:], p[:, 1:]) if len(g) and len(p) else np.zeros((len(g), len(p)))
        for a, b in zip(*np.where(m >= umbral)):
            co[gi[a], pi[b]] += 1
        vistos |= set(pi)
        # se mantiene el emparejamiento anterior si sigue válido; el resto, asignación húngara
        pares = []
        for a, g_ in enumerate(gi):
            b = pi.index(mapa[g_]) if mapa.get(g_) in pi else None
            if b is not None and b not in {y for _, y in pares} and m[a, b] >= umbral:
                pares.append((a, b))
        ra = [a for a in range(len(gi)) if a not in {x for x, _ in pares}]
        rb = [b for b in range(len(pi)) if b not in {y for _, y in pares}]
        if ra and rb:
            costo = np.where(m[np.ix_(ra, rb)] >= umbral, 1 - m[np.ix_(ra, rb)], 1e6)
            pares += [(ra[x], rb[y]) for x, y in zip(*linear_sum_assignment(costo)) if costo[x, y] < 1e6]
        ok = set()
        for a, b in pares:
            c["IDSW"] += gi[a] in mapa and mapa[gi[a]] != pi[b]
            mapa[gi[a]] = pi[b]
            c["suma_iou"] += m[a, b]
            ok.add(gi[a])
        c["TP"] += len(pares)
        c["FP"] += len(pi) - len(pares)
        c["FN"] += len(gi) - len(pares)
        for g_ in gi:
            vivo[g_] += 1
            seguido[g_] += g_ in ok
            c["Frag"] += g_ in ok and previo.get(g_) is False and seguido[g_] > 1
            previo[g_] = g_ in ok
    if co:  # IDF1: cada pez del GT se asocia a un solo ID del tracker
        G, P = sorted({g for g, _ in co}), sorted({p for _, p in co})
        mat = np.zeros((len(G), len(P)))
        for (g_, p_), n in co.items():
            mat[G.index(g_), P.index(p_)] = n
        r, k = linear_sum_assignment(-mat)
        c["IDTP"] = mat[r, k].sum()
    frac = [seguido[g] / vivo[g] for g in vivo]
    c.update(n_gt=sum(vivo.values()), n_pred=c["TP"] + c["FP"], peces_gt=len(vivo), ids_tracker=len(vistos),
             MT=sum(x >= 0.8 for x in frac), ML=sum(x < 0.2 for x in frac))
    return c


def metricas(c: dict) -> dict:
    n_gt = max(c["n_gt"], 1)
    return dict(
        IDF1=round(2 * c["IDTP"] / max(c["n_gt"] + c["n_pred"], 1), 4), IDSW=int(c["IDSW"]),
        MOTA=round(1 - (c["FN"] + c["FP"] + c["IDSW"]) / n_gt, 4), MOTP=round(c["suma_iou"] / max(c["TP"], 1), 4),
        FP=int(c["FP"]), FN=int(c["FN"]), Frag=int(c["Frag"]), MT=int(c["MT"]), ML=int(c["ML"]),
        peces_gt=int(c["peces_gt"]), ids_tracker=int(c["ids_tracker"]),
    )


def detectar(cfg: dict, perfil: dict, cuadros: list, gt: dict, oraculo: bool) -> list[list[dict]]:
    if oraculo:
        return [[dict(x1=x, y1=y, x2=x + w, y2=y + h, conf=1.0) for _, x, y, w, h in gt.get(f, VACIO)]
                for f, _ in cuadros]
    from tracker.detector import Detector

    detector = Detector(cfg, perfil)
    return [detector.detectar(cv2.imread(str(r))) for _, r in cuadros]


def seguir(perfil: dict, cuadros: list, dets: list, ancho: int, alto: int) -> dict[int, np.ndarray]:
    from tracker.seguimiento import crear_seguidor

    seguidor = crear_seguidor({}, perfil, [Canal("cuadro", (0, 0, ancho, alto))])
    pred = {}
    for (f, _), d in zip(cuadros, dets):
        filas = [[t["id"], t["x1"], t["y1"], t["x2"] - t["x1"], t["y2"] - t["y1"]] for t in seguidor.actualizar(f, d)]
        if filas:
            pred[f] = np.array(filas)
    return pred


def evaluar(cfg: dict, perfil: dict, seqs: list[str], trackers: list[str], salida: Path,
            oraculo: bool = False) -> list[dict]:
    """Filas por secuencia y una fila TOTAL por tracker (métricas sobre la suma de las secuencias)."""
    filas, sumas = [], {t: defaultdict(float) for t in trackers}
    for seq in seqs:
        gt, cuadros = leer_mot(dir_gt(cfg, seq) / "gt" / "gt.txt"), cuadros_seq(cfg, seq)
        alto, ancho = cv2.imread(str(cuadros[0][1])).shape[:2]
        dets = detectar(cfg, perfil, cuadros, gt, oraculo)
        for t in trackers:
            p = {**perfil, "tracker": {**perfil["tracker"], "tipo": leer_yaml(ruta_abs(t))["tracker_type"], "config": t}}
            pred = seguir(p, cuadros, dets, ancho, alto)
            (salida / "trayectorias" / Path(t).stem).mkdir(parents=True, exist_ok=True)
            (salida / "trayectorias" / Path(t).stem / f"{seq}.txt").write_text(
                "\n".join(f"{f},{int(i)},{x:.1f},{y:.1f},{w:.1f},{h:.1f},1,-1,-1,-1"
                          for f in sorted(pred) for i, x, y, w, h in pred[f]), encoding="utf-8")
            c = acumular(gt, pred, [f for f, _ in cuadros])
            for k, v in c.items():
                sumas[t][k] += v
            filas.append(dict(tracker=Path(t).stem, secuencia=seq, **metricas(c)))
            print(f"  {seq} {Path(t).stem:10s} IDF1 {filas[-1]['IDF1']:.1%}  IDSW {filas[-1]['IDSW']}")
    totales = [dict(tracker=Path(t).stem, secuencia="TOTAL", **metricas(sumas[t])) for t in trackers]
    filas += sorted(totales, key=lambda r: -r["IDF1"])
    salida.mkdir(parents=True, exist_ok=True)
    with open(salida / "metricas.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(COLUMNAS)
        w.writerows([fmt(r[k]) if k in ("IDF1", "MOTA") else r[k] for k in COLUMNAS.values()] for r in filas)
    return filas


COLUMNAS = {  # encabezado del CSV -> métrica
    "TRACKER": "tracker", "SEQUENCE": "secuencia", "PERCENTAGE OF CORRECT IDs": "IDF1",
    "TIMES ID CHANGED": "IDSW", "OVERALL TRACKING ACCURACY (MOTA)": "MOTA", "EXTRA BOXES": "FP",
    "MISSING BOXES": "FN", "Frag": "Frag", "MT": "MT", "ML": "ML", "TOTAL FISHES": "peces_gt",
    "FISHES COUNTED BY TRACKER": "ids_tracker",
}


def fmt(v: float) -> str:
    """0.6063 -> '60.63%', 0.25 -> '25%'."""
    return f"{round(100 * float(v), 2):g}%"
