"""Punto de entrada: `uv run tracker`.

    uv run tracker                                   # abre la aplicación
    uv run tracker inferir --video v.mp4 --salida outputs/v        # solo detector: detecciones guardadas
    uv run tracker procesar --video v.mp4 --canales c.json --salida outputs/v [--perfil base] [--tracker configs/ocsort.yaml]
    uv run tracker validar outputs/v                 # comprueba una carpeta contra el formato común
    uv run tracker evaluar-seguimiento --conjunto val [--trackers configs/bytetrack.yaml configs/ocsort.yaml ...] [--oraculo]
"""
import argparse
import sys
from pathlib import Path

from tracker import formato
from tracker.canales import Canal, cargar_canales
from tracker.pipeline import cargar_perfil, info_video, procesar
from tracker.seguimiento import con_tracker


def _avance(av) -> None:
    if av.cuadro % 25 == 0:
        total = f"/{av.total}" if av.total else ""
        print(f"\r  cuadro {av.cuadro + 1}{total}  detecciones {len(av.detecciones)}", end="", flush=True)


def _ejecutar(video: str, canales: list[Canal], perfil, salida: str, solo_detectar: bool) -> int:
    res = procesar(video, canales, perfil, solo_detectar=solo_detectar, al_avanzar=_avance)
    carpeta = formato.exportar(res, salida)
    print(f"\n[OK] {len(res.detecciones)} detecciones, {len(res.eventos)} eventos -> {carpeta}")
    for canal, n in res.conteos.items():
        print(f"  {canal}: {n}")
    return 0


def _evaluar_seguimiento(a) -> int:
    from comun import cargar_config, ruta_abs, secuencias
    from tracker.evaluar_seguimiento import con_gt, evaluar
    from tracker.pipeline import cargar_perfil

    cfg = cargar_config()
    perfil = cargar_perfil(a.perfil)
    disponibles = con_gt(cfg)
    seqs = a.seq or [s for s in secuencias(cfg, a.conjunto) if s in disponibles]
    if not seqs:
        raise ValueError(f"No hay secuencias de '{a.conjunto}' con gt.txt en {cfg['rutas']['tracking']}")
    trackers = a.trackers or [perfil["tracker"]["config"]]
    salida = ruta_abs(cfg["rutas"]["salidas"]) / "evaluacion_seguimiento" / (perfil["nombre"] + ("_oraculo" if a.oraculo else ""))
    filas = evaluar(cfg, perfil, seqs, trackers, salida, a.oraculo)
    print("=" * 60)
    for r in filas:
        if r["secuencia"] == "TOTAL":
            print(f"  {r['tracker']:10s} IDF1 {r['IDF1']:.1%} | IDSW {r['IDSW']} | MOTA {r['MOTA']:.1%} | "
                  f"conteo {r['conteo_tracker']} vs referencia {r['conteo_referencia']} (error {r['error_conteo']})")
    print(f"  Salidas : {salida}")
    print("=" * 60)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tracker", description="Contador de salmones por canal.")
    sub = p.add_subparsers(dest="orden")
    inf = sub.add_parser("inferir", help="solo el detector, sobre todo el video")
    inf.add_argument("--video", required=True)
    inf.add_argument("--salida", required=True)
    inf.add_argument("--perfil", default="base")
    pro = sub.add_parser("procesar", help="detector + seguimiento + conteo por canal")
    pro.add_argument("--video", required=True)
    pro.add_argument("--canales", required=True, help="JSON guardado por la interfaz")
    pro.add_argument("--salida", required=True)
    pro.add_argument("--perfil", default="base")
    pro.add_argument("--tracker", help="YAML de otro tracker (bytetrack, botsort, ocsort, deepsort); reemplaza el del perfil")
    val = sub.add_parser("validar", help="valida una carpeta del formato común")
    val.add_argument("carpeta")
    evs = sub.add_parser("evaluar-seguimiento", help="IDF1, ID switches y MOTA contra las trayectorias de DAT-02")
    evs.add_argument("--conjunto", default="val")
    evs.add_argument("--seq", nargs="+", help="secuencias concretas (en vez de --conjunto)")
    evs.add_argument("--perfil", default="base", help="detector; el tracker lo eligen --trackers")
    evs.add_argument("--trackers", nargs="+", help="YAMLs a comparar; por defecto el del perfil")
    evs.add_argument("--oraculo", action="store_true", help="cajas del GT en vez del detector")
    a = p.parse_args(argv)

    try:
        if a.orden == "evaluar-seguimiento":
            return _evaluar_seguimiento(a)
        if a.orden == "validar":
            errores = formato.validar(a.carpeta)
            print("\n".join(errores) if errores else "[OK] La carpeta cumple el formato común.")
            return 1 if errores else 0
        if a.orden == "inferir":
            info = info_video(a.video)  # falla con mensaje claro si el video no abre
            todo = Canal("canal_1", (0, 0, info["ancho"], info["alto"]), "cuadro completo")
            return _ejecutar(a.video, [todo], a.perfil, a.salida, solo_detectar=True)
        if a.orden == "procesar":
            perfil = cargar_perfil(a.perfil)
            if a.tracker:
                perfil = con_tracker(perfil, a.tracker)
            return _ejecutar(a.video, cargar_canales(a.canales), perfil, a.salida, solo_detectar=False)
    except (ValueError, FileNotFoundError, NotImplementedError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    from tracker.gui.app import ejecutar  # import tardío: la CLI no necesita Qt

    return ejecutar()


if __name__ == "__main__":
    raise SystemExit(main())
