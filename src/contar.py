"""Cuenta salmones: detector YOLO11 -> seguimiento ByteTrack -> cruce de línea virtual hacia abajo.

Entrada: un video, una carpeta de cuadros o una secuencia de data/ (--seq).
Salida en outputs/<nombre>/: anotado.mp4, eventos.csv (una fila por caja seguida y cuadro),
cruces.csv (un evento por salmón contado) y resumen.json con el conteo.

Regla de conteo (Avance 1): línea horizontal a una fracción del alto; un salmón suma 1 cuando
el centro de su caja pasa de estar sobre la línea a estar en ella o bajo ella, o cuando se ve
por primera vez en la línea o bajo ella (ya la pasó entre cuadros no vistos, p. ej. tras un salto
de numeración) sin moverse hacia arriba. Cada ID cuenta una sola vez y los cruces hacia arriba no cuentan.

Uso:
    uv run python src/contar.py --video clip.mp4
    uv run python src/contar.py --seq seq_0002 --linea 0.4
    uv run python src/contar.py --seq seq_0003 --oraculo    # cajas etiquetadas en vez del detector
"""
import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from comun import (
    cargar_config, dir_datos, dispositivo, imgsz_de_pesos, ir_a_raiz, leer_etiquetas_xyxy,
    leer_yaml, listar_cuadros, ruta_abs, sha256,
)

CAMPOS = ["paso", "cuadro", "segmento", "id", "x1", "y1", "x2", "y2", "conf", "cx", "cy"]


# ----------------------------------------------------------------------------- fuentes
def leer_fuente(video: str | None = None, cuadros: str | None = None):
    """Itera (número de cuadro, imagen BGR, ruta o None). En un video los números son consecutivos."""
    if video:
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            raise SystemExit(f"[ERROR] No se pudo abrir el video: {video}")
        i = 0
        try:
            while True:
                ok, img = cap.read()
                if not ok:
                    break
                yield i, img, None
                i += 1
        finally:
            cap.release()
    else:
        for num, ruta in listar_cuadros(Path(cuadros)):
            img = cv2.imread(str(ruta))
            if img is None:
                print(f"[AVISO] Cuadro ilegible, se omite: {ruta.name}")
                continue
            yield num, img, ruta


def fps_fuente(cfg: dict, video: str | None) -> float:
    if video:
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        if fps and not np.isnan(fps) and fps > 0:
            return float(fps)
    return float(cfg["conteo"]["fps_cuadros"])


# ----------------------------------------------------------------------------- detección
def detectar_fuente(cfg: dict, video=None, cuadros=None, pesos=None, oraculo=False) -> tuple[list, dict]:
    """Primera pasada: cajas de cada cuadro, del detector o (oráculo) de las etiquetas.

    Se guardan para poder seguir varias veces con distintos parámetros sin volver a detectar.
    """
    from ultralytics.engine.results import Boxes

    yolo = imgsz = disp = None
    if not oraculo:
        from ultralytics import YOLO

        yolo = YOLO(str(pesos))
        imgsz = imgsz_de_pesos(Path(pesos))
        disp = dispositivo(cfg)
    c = cfg["conteo"]
    dets, alto, ancho = [], None, None
    for paso, (num, img, ruta) in enumerate(leer_fuente(video, cuadros)):
        alto, ancho = img.shape[:2]
        if oraculo:
            xyxy = leer_etiquetas_xyxy(ruta.parent.parent / "labels" / f"{ruta.stem}.txt", ancho, alto)
            datos = np.zeros((len(xyxy), 6), dtype=np.float32)
            datos[:, :4], datos[:, 4] = xyxy, 1.0  # confianza 1, clase 0
            cajas = Boxes(datos, (alto, ancho))
        else:
            cajas = yolo.predict(img, imgsz=imgsz, conf=float(c["conf_detector"]), iou=float(c["iou_nms"]),
                                 device=disp, verbose=False)[0].boxes.cpu().numpy()
        dets.append((paso, num, cajas))
    if not dets:
        raise SystemExit("[ERROR] La fuente no tiene cuadros.")
    return dets, dict(pasos=len(dets), alto=alto, ancho=ancho, imgsz=imgsz, fps=fps_fuente(cfg, video))


# ----------------------------------------------------------------------------- seguimiento
def nuevo_tracker(cfg: dict, match_thresh: float | None = None):
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.utils import IterableSimpleNamespace

    args = leer_yaml(ruta_abs(cfg["conteo"]["tracker"]))
    args["match_thresh"] = float(match_thresh if match_thresh is not None else cfg["conteo"]["match_thresh"])
    return BYTETracker(IterableSimpleNamespace(**args))


def seguir(cfg: dict, dets: list, match_thresh: float | None = None) -> tuple[list[dict], int]:
    """Segunda etapa: ByteTrack sobre las cajas. Devuelve una fila por caja seguida y los segmentos.

    Si entre dos cuadros faltan más de 'salto_reinicio' números, se crea un tracker nuevo
    (segmento nuevo): tras ese salto los peces en pantalla ya no son los mismos y
    mantener los IDs solo permitiría asociaciones equivocadas.
    """
    salto = int(cfg["conteo"]["salto_reinicio"])
    registros, tracker, segmento, previo = [], nuevo_tracker(cfg, match_thresh), 0, None
    for paso, num, cajas in dets:
        if previo is not None and salto > 0 and num - previo > salto:
            tracker, segmento = nuevo_tracker(cfg, match_thresh), segmento + 1
        previo = num
        for x1, y1, x2, y2, tid, conf, *_ in tracker.update(cajas):  # también sin cajas: los IDs perdidos envejecen
            registros.append(dict(
                paso=paso, cuadro=num, segmento=segmento, id=int(tid),
                x1=round(float(x1), 1), y1=round(float(y1), 1), x2=round(float(x2), 1), y2=round(float(y2), 1),
                conf=round(float(conf), 4), cx=round(float(x1 + x2) / 2, 1), cy=round(float(y1 + y2) / 2, 1),
            ))
    return registros, segmento + 1


# ----------------------------------------------------------------------------- conteo
def contar_cruces(registros: list[dict], y_linea: float) -> list[dict]:
    """Eventos de conteo, una vez por ID: cruce hacia abajo (centro previo < línea <= centro actual) o
    ID visto por primera vez en la línea o bajo ella (el pez ya la pasó entre cuadros no vistos) sin
    desplazamiento neto hacia arriba.

    El ID es (segmento, id): al reiniciar el tracker los números vuelven a empezar.
    """
    ultimo_cy = {(r["segmento"], r["id"]): r["cy"] for r in registros}
    previo, contados, cruces = {}, set(), []
    for r in registros:
        clave = (r["segmento"], r["id"])
        if clave in contados:
            previo[clave] = r["cy"]
            continue
        if clave in previo:
            cuenta = previo[clave] < y_linea <= r["cy"]
        else:
            cuenta = r["cy"] >= y_linea and ultimo_cy[clave] >= r["cy"]
        if cuenta:
            contados.add(clave)
            cruces.append(dict(paso=r["paso"], cuadro=r["cuadro"], segmento=r["segmento"], id=r["id"],
                               conteo=len(contados)))
        previo[clave] = r["cy"]
    return cruces


# ----------------------------------------------------------------------------- salida
def escribir_video(ruta: Path, cfg: dict, registros, cruces, info, y_linea: int, fraccion: float,
                   video=None, cuadros=None) -> None:
    """Segunda pasada: dibuja línea, cajas, IDs y conteo acumulado."""
    por_paso: dict[int, list] = {}
    for r in registros:
        por_paso.setdefault(r["paso"], []).append(r)
    cruce_en = {c["paso"]: c["conteo"] for c in cruces}
    contado_desde = {(c["segmento"], c["id"]): c["paso"] for c in cruces}

    out = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), info["fps"], (info["ancho"], info["alto"]))
    if not out.isOpened():
        raise SystemExit(f"[ERROR] No se pudo crear el video {ruta}")
    conteo = 0
    for paso, (num, img, _) in enumerate(leer_fuente(video, cuadros)):
        conteo = cruce_en.get(paso, conteo)
        cv2.line(img, (0, y_linea), (info["ancho"], y_linea), (0, 255, 255), 3)
        cv2.putText(img, f"Linea {int(round(fraccion * 100))}%", (15, y_linea - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        for r in por_paso.get(paso, []):
            ya = contado_desde.get((r["segmento"], r["id"]), 10**9) <= paso
            color = (0, 200, 0) if ya else (255, 120, 0)
            p1, p2 = (int(r["x1"]), int(r["y1"])), (int(r["x2"]), int(r["y2"]))
            cv2.rectangle(img, p1, p2, color, 2)
            cv2.circle(img, (int(r["cx"]), int(r["cy"])), 5, (0, 0, 255), -1)
            cv2.putText(img, f"ID {r['segmento']}-{r['id']} {r['conf']:.2f}", (p1[0], max(22, p1[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.rectangle(img, (0, 0), (info["ancho"], 52), (0, 0, 0), -1)
        cv2.putText(img, f"Cuadro {num} | Salmones contados: {conteo}", (15, 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        out.write(img)
    out.release()


def contar(cfg: dict, video=None, cuadros=None, pesos=None, lineas=None, oraculo=False,
           nombre=None, con_video=True, guardar=True, detecciones=None) -> dict:
    """Detecta, sigue una vez y cuenta para cada línea pedida. Devuelve {linea: conteo} y rutas de salida.

    'detecciones' = (dets, info) ya calculadas con detectar_fuente, para no repetir la detección.
    """
    ir_a_raiz()
    if not video and not cuadros:
        raise SystemExit("[ERROR] Indique --video, --cuadros o --seq.")
    if oraculo and not cuadros:
        raise SystemExit("[ERROR] --oraculo necesita cuadros con su carpeta labels/ al lado.")
    pesos = Path(pesos) if pesos else ruta_abs(cfg["rutas"]["pesos"]) / "best.pt"
    if not oraculo and not pesos.exists():
        raise SystemExit(f"[ERROR] No se encontraron los pesos '{pesos}'. Ejecute antes src/grilla.py.")
    lineas = [float(x) for x in (lineas or [cfg["conteo"]["linea"]])]
    if not all(0 < x < 1 for x in lineas):
        raise SystemExit("[ERROR] La línea es una fracción del alto entre 0 y 1.")

    dets, info = detecciones or detectar_fuente(cfg, video, cuadros, pesos, oraculo)
    info = dict(info)
    registros, info["segmentos"] = seguir(cfg, dets)
    resultado = {"fuente": str(video or cuadros), "oraculo": oraculo, "pasos": info["pasos"],
                 "segmentos": info["segmentos"], "match_thresh": float(cfg["conteo"]["match_thresh"]),
                 "pesos": None if oraculo else str(pesos),
                 "sha256_pesos": None if oraculo else sha256(pesos), "conteos": {}}
    cruces_por_linea = {}
    for f in lineas:
        y = int(round(info["alto"] * f))
        cruces_por_linea[f] = contar_cruces(registros, y)
        resultado["conteos"][f"{f:.2f}"] = len(cruces_por_linea[f])

    if guardar:
        nombre = nombre or (Path(video).stem if video else Path(cuadros).parent.name)
        carpeta = ruta_abs(cfg["rutas"]["salidas"]) / (nombre + ("_oraculo" if oraculo else ""))
        carpeta.mkdir(parents=True, exist_ok=True)
        with open(carpeta / "eventos.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            w.writerows(registros)
        with open(carpeta / "cruces.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["linea", "paso", "cuadro", "segmento", "id", "conteo"])
            w.writeheader()
            for fr, cr in cruces_por_linea.items():
                w.writerows({"linea": f"{fr:.2f}", **c} for c in cr)
        if con_video:
            f0 = lineas[0]
            ruta_video = carpeta / "anotado.mp4"
            escribir_video(ruta_video, cfg, registros, cruces_por_linea[f0], info,
                           int(round(info["alto"] * f0)), f0, video, cuadros)
            resultado["video"] = str(ruta_video)
        (carpeta / "resumen.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
        resultado["carpeta"] = str(carpeta)
    return resultado


def resolver_cuadros(cfg: dict, seq: str | None, cuadros: str | None) -> str | None:
    if seq:
        return str(dir_datos(cfg) / seq / "images")
    return cuadros


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Conteo automático de salmones.")
    fuente = p.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--video", help="archivo de video")
    fuente.add_argument("--cuadros", help="carpeta de cuadros (images/, con labels/ al lado para --oraculo)")
    fuente.add_argument("--seq", help="secuencia de data/, p. ej. seq_0003")
    p.add_argument("--config", default=None)
    p.add_argument("--pesos", default=None, help="por defecto weights/best.pt")
    p.add_argument("--linea", type=float, nargs="+", default=None,
                   help="fracción del alto (una o varias); el video usa la primera. Por defecto la de config")
    p.add_argument("--oraculo", action="store_true", help="usar las cajas etiquetadas en vez del detector")
    p.add_argument("--nombre", default=None, help="subcarpeta de outputs/")
    p.add_argument("--sin-video", action="store_true", help="no escribir el video anotado")
    a = p.parse_args()

    cfg = cargar_config(a.config)
    fuente_v = str(Path(a.video).resolve()) if a.video else None
    fuente_c = resolver_cuadros(cfg, a.seq, str(Path(a.cuadros).resolve()) if a.cuadros else None)
    pesos = str(Path(a.pesos).resolve()) if a.pesos else None
    r = contar(cfg, fuente_v, fuente_c, pesos, a.linea, a.oraculo, a.nombre, not a.sin_video)
    print("=" * 60)
    print(f"  Fuente     : {r['fuente']}" + ("  [ORÁCULO: cajas etiquetadas]" if r["oraculo"] else ""))
    print(f"  Cuadros    : {r['pasos']} | segmentos de seguimiento: {r['segmentos']}")
    for linea, n in r["conteos"].items():
        print(f"  Línea {linea} : {n} salmones")
    print(f"  Salidas    : {r['carpeta']}")
    print("=" * 60)
