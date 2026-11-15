"""Punto de entrada: `uv run tracker`.

    uv run tracker                                   # abre la aplicación
    uv run tracker inferir --video v.mp4 --salida outputs/v        # solo detector: detecciones guardadas
    uv run tracker procesar --video v.mp4 --canales c.json --salida outputs/v [--perfil base]
    uv run tracker validar outputs/v                 # comprueba una carpeta contra el formato común
"""
import argparse
import sys
from pathlib import Path

from tracker import formato
from tracker.canales import Canal, cargar_canales
from tracker.pipeline import info_video, procesar


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
    val = sub.add_parser("validar", help="valida una carpeta del formato común")
    val.add_argument("carpeta")
    a = p.parse_args(argv)

    try:
        if a.orden == "validar":
            errores = formato.validar(a.carpeta)
            print("\n".join(errores) if errores else "[OK] La carpeta cumple el formato común.")
            return 1 if errores else 0
        if a.orden == "inferir":
            info = info_video(a.video)  # falla con mensaje claro si el video no abre
            todo = Canal("canal_1", (0, 0, info["ancho"], info["alto"]), "cuadro completo")
            return _ejecutar(a.video, [todo], a.perfil, a.salida, solo_detectar=True)
        if a.orden == "procesar":
            return _ejecutar(a.video, cargar_canales(a.canales), a.perfil, a.salida, solo_detectar=False)
    except (ValueError, FileNotFoundError, NotImplementedError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    from tracker.gui.app import ejecutar  # import tardío: la CLI no necesita Qt

    return ejecutar()


if __name__ == "__main__":
    raise SystemExit(main())
