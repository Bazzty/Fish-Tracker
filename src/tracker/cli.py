"""Punto de entrada: `uv run tracker`.

    uv run tracker                                   # abre la aplicación
    uv run tracker inferir --video v.mp4             # solo detector -> outputs/deteccion/<detector>/<secuencia>/
    uv run tracker procesar --video v.mp4 --canales dos_tubos [--conteo linea_simple]
                                                     # [--tracker configs/ocsort.yaml] [--fps 5 (video anotado)]
                                                     # -> outputs/seguimiento/... y outputs/conteo/... con anotado.mp4
    uv run tracker validar outputs/conteo/<...>      # comprueba una carpeta contra el formato común
    uv run tracker evaluar-seguimiento --conjunto val [--trackers configs/bytetrack.yaml configs/ocsort.yaml ...] [--oraculo]
    uv run tracker comparar "Base=<metricas>.json" "Variante=<metricas>.json[:tracker]" [--salida tabla.md]

Perfil: variante (YOLO26 + OC-SORT de configs/tracker_variante.yaml + dos líneas). La línea base del plan
(YOLO11 + ByteTrack + línea simple) quedó en la rama comparacion-yolo11-base.
--canales acepta una ruta o el nombre de un JSON de configs/ (dos_tubos = configs/canales_dos_tubos.json).
La secuencia se toma de --seq o del nombre del video (seq_00015.mp4 -> seq_00015); si tiene DAT-02, conteo.json
trae también el conteo real.
"""
import argparse
import sys
from pathlib import Path

from comun import cargar_config, dir_datos, listar_cuadros, secuencias
from tracker import formato
from tracker.canales import Canal, cargar_canales, ruta_canales
from tracker.pipeline import PERFIL_POR_DEFECTO, cargar_perfil, info_video, procesar
from tracker.salidas import (carpeta, con_conteo, escribir_conteo, escribir_seguimiento, nombre_detector,
                             nombre_regla, nombre_tracker)
from tracker.seguimiento import con_tracker


def _avance(av) -> None:
    if av.cuadro % 25 == 0:
        total = f"/{av.total}" if av.total else ""
        print(f"\r  cuadro {av.cuadro + 1}{total}  detecciones {len(av.detecciones)}", end="", flush=True)


def _imagenes(cfg: dict, seq: str) -> list[str]:
    """Nombre del archivo de cada cuadro (el video de secuencia_a_video.py sigue este orden)."""
    imgs = dir_datos(cfg) / seq / "images"
    return [r.name for _, r in listar_cuadros(imgs)] if imgs.is_dir() and any(imgs.iterdir()) else []


def _inferir(a) -> int:
    cfg = cargar_config()
    perfil = cargar_perfil(a.perfil)
    info = info_video(a.video)  # falla con mensaje claro si el video no abre
    seq = a.seq or Path(a.video).stem
    salida = Path(a.salida) if a.salida else carpeta(cfg, "deteccion", nombre_detector(perfil), seq)
    todo = Canal("canal_1", (0, 0, info["ancho"], info["alto"]), "cuadro completo")
    res = procesar(a.video, [todo], perfil, solo_detectar=True, al_avanzar=_avance, cfg=cfg)
    formato.exportar(res, salida)
    print(f"\n[OK] {len(res.detecciones)} detecciones -> {salida}")
    return 0


def _procesar(a) -> int:
    from tracker.evaluar_seguimiento import con_gt, conteo_referencia

    cfg = cargar_config()
    perfil = con_conteo(cargar_perfil(a.perfil), a.conteo)
    if a.tracker:
        perfil = con_tracker(perfil, a.tracker)
    canales = cargar_canales(ruta_canales(a.canales))
    seq = a.seq or Path(a.video).stem
    res = procesar(a.video, canales, perfil, al_avanzar=_avance, cfg=cfg)
    referencia = conteo_referencia(cfg, seq, canales) if seq in con_gt(cfg) else None
    imagenes = _imagenes(cfg, seq)

    modelo = f"{nombre_detector(perfil)}_{nombre_tracker(perfil)}"
    if a.salida:  # todo en una carpeta (formato común + los dos JSON)
        d_seguimiento = d_conteo = Path(a.salida)
    else:
        d_seguimiento = carpeta(cfg, "seguimiento", modelo, seq)
        d_conteo = carpeta(cfg, "conteo", modelo, seq, nombre_regla(perfil))
    formato.exportar(res, d_conteo)
    escribir_seguimiento(d_seguimiento / "seguimiento.json", res, perfil, seq, a.video, imagenes)
    escribir_conteo(d_conteo / "conteo.json", res, perfil, seq, a.video, imagenes, referencia)
    video = None
    if not a.sin_video:
        from tracker.video import anotar

        print("\n  Dibujando el video anotado ...", end="", flush=True)
        video = anotar(res, a.video, d_conteo / "anotado.mp4", nombre_regla(perfil) == "dos_lineas", a.fps)

    print(f"\n[OK] {seq} | modelo {modelo} | conteo {nombre_regla(perfil)}")
    for c, n in res.conteos.items():
        real = f" | real {referencia[c]} (error {abs(n - referencia[c])})" if referencia else ""
        print(f"  {c}: contados {n}{real}")
    if referencia is None:
        print("  (sin conteo real: la secuencia no tiene gt.txt en DAT-02)")
    print(f"  Seguimiento: {(d_seguimiento / 'seguimiento.json').resolve()}")
    print(f"  Conteo     : {(d_conteo / 'conteo.json').resolve()} (+ formato común)")
    print(f"  Video      : {video.resolve() if video else 'no se generó (--sin-video)'}")
    return 0


def _evaluar_seguimiento(a) -> int:
    from tracker.evaluar_seguimiento import con_gt, evaluar

    cfg = cargar_config()
    perfil = con_conteo(cargar_perfil(a.perfil), a.conteo)
    disponibles = con_gt(cfg)
    seqs = a.seq or [s for s in secuencias(cfg, a.conjunto) if s in disponibles]
    if not seqs:
        raise ValueError(f"No hay secuencias de '{a.conjunto}' con gt.txt en {cfg['rutas']['tracking']}")
    trackers = a.trackers or [perfil["tracker"]["config"]]
    grupo = (a.conjunto if not a.seq else "_".join(seqs) if len(seqs) <= 3 else f"{len(seqs)}_secuencias")
    grupo = f"{grupo}_{nombre_regla(perfil)}"
    salida = carpeta(cfg, "evaluacion_seguimiento", nombre_detector(perfil, a.oraculo))
    filas = evaluar(cfg, perfil, seqs, trackers, salida, a.oraculo, grupo)
    print("=" * 60)
    for r in filas:
        if r["secuencia"] == "TOTAL":
            print(f"  {r['tracker']:10s} IDF1 {r['IDF1']:.1%} | IDSW {r['IDSW']} | MOTA {r['MOTA']:.1%} | "
                  f"conteo {r['conteo_tracker']} vs referencia {r['conteo_referencia']} (error {r['error_conteo']})")
    print(f"  Métricas: {salida / f'metricas_{grupo}.csv'} (y .json)")
    print("=" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tracker", description="Contador de salmones por canal.")
    sub = p.add_subparsers(dest="orden")
    inf = sub.add_parser("inferir", help="solo el detector, sobre todo el video")
    inf.add_argument("--video", required=True)
    inf.add_argument("--seq", help="nombre de la secuencia (por defecto, el del video)")
    inf.add_argument("--salida", help="carpeta de salida (por defecto outputs/deteccion/<detector>/<secuencia>)")
    inf.add_argument("--perfil", default=PERFIL_POR_DEFECTO, help="nombre o YAML de configs/perfiles (por defecto variante)")
    pro = sub.add_parser("procesar", help="detector + seguimiento + conteo por canal")
    pro.add_argument("--video", required=True)
    pro.add_argument("--canales", required=True, help="JSON de tubos: ruta o nombre en configs/ (p. ej. dos_tubos)")
    pro.add_argument("--seq", help="nombre de la secuencia (por defecto, el del video); con DAT-02 da el conteo real")
    pro.add_argument("--salida", help="todo en esta carpeta (por defecto outputs/seguimiento/... y outputs/conteo/...)")
    pro.add_argument("--perfil", default=PERFIL_POR_DEFECTO,
                     help="nombre o YAML de configs/perfiles (por defecto variante: YOLO26 + OC-SORT + dos líneas)")
    pro.add_argument("--tracker", help="YAML de otro tracker (bytetrack, botsort, ocsort, deepsort); reemplaza el del perfil")
    pro.add_argument("--sin-video", action="store_true", help="no dibujar el video anotado (más rápido)")
    pro.add_argument("--fps", type=float, help="fps del video anotado (por defecto, los del video); no cambia el conteo")
    pro.add_argument("--conteo", choices=["linea_simple", "dos_lineas"], help="regla de conteo (por defecto la del perfil)")
    val = sub.add_parser("validar", help="valida una carpeta del formato común")
    val.add_argument("carpeta")
    evs = sub.add_parser("evaluar-seguimiento", help="IDF1, ID switches y MOTA contra las trayectorias de DAT-02")
    evs.add_argument("--conjunto", default="val")
    evs.add_argument("--seq", nargs="+", help="secuencias concretas (en vez de --conjunto)")
    evs.add_argument("--perfil", default=PERFIL_POR_DEFECTO,
                     help="detector y regla de conteo (por defecto variante); el tracker lo eligen --trackers")
    evs.add_argument("--trackers", nargs="+", help="YAMLs a comparar; por defecto el del perfil")
    evs.add_argument("--oraculo", action="store_true", help="cajas del GT en vez del detector")
    evs.add_argument("--conteo", choices=["linea_simple", "dos_lineas"], help="regla de conteo (por defecto la del perfil)")
    cmp = sub.add_parser("comparar", help="tabla de error de conteo entre configuraciones (metricas_*.json)")
    cmp.add_argument("entradas", nargs="+", help="ETIQUETA=RUTA.json o ETIQUETA=RUTA.json:TRACKER")
    cmp.add_argument("--salida", help="guarda la tabla Markdown en este archivo")
    cmp.add_argument("--titulo", help="título de la tabla")
    a = p.parse_args(argv)

    try:
        if a.orden == "evaluar-seguimiento":
            return _evaluar_seguimiento(a)
        if a.orden == "comparar":
            from tracker.comparar import comparar

            print(comparar(a.entradas, a.salida, a.titulo))
            return 0
        if a.orden == "validar":
            errores = formato.validar(a.carpeta)
            print("\n".join(errores) if errores else "[OK] La carpeta cumple el formato común.")
            return 1 if errores else 0
        if a.orden == "inferir":
            return _inferir(a)
        if a.orden == "procesar":
            return _procesar(a)
    except (ValueError, FileNotFoundError, NotImplementedError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    from tracker.gui.app import ejecutar  # import tardío: la CLI no necesita Qt

    return ejecutar()


if __name__ == "__main__":
    raise SystemExit(main())
