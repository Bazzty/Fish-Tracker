"""Criterio de éxito del Avance 1, calculado a partir de los pesos entregados.

  Condición previa : mAP@0.5 en validación >= criterio.map50_val_min (0.90)
  Criterio principal: error relativo del conteo sobre el TOTAL de test <= criterio.error_relativo_max (10 %)
  El error de cada secuencia se reporta solo como información, sin umbral.

  error absoluto = |contados - reales|      error relativo = error absoluto / reales

Modos:
    uv run python src/criterio.py --split val             # elegir línea y match_thresh (no usa test)
    uv run python src/criterio.py --split val --oraculo   # ¿el seguimiento pierde peces con cajas perfectas?
    uv run python src/criterio.py                         # veredicto final en test (una sola vez)
    uv run python src/criterio.py --oraculo               # análisis de casos: separa detector de seguimiento
"""
import argparse
import csv
import json

from pathlib import Path

from comun import cargar_config, conteo_real, dir_datos, relativa, ruta_abs, secuencias
from contar import contar, contar_cruces, detectar_fuente, seguir
from evaluar import evaluar


def tabla_conteo(cfg: dict, split: str, lineas: list[float], matches: list[float], pesos, oraculo: bool,
                 videos: bool) -> dict:
    """Cuenta cada secuencia del conjunto para cada combinación (match_thresh, línea).

    Se detecta una vez por secuencia. Con la combinación de config.yaml se guardan además
    eventos.csv, cruces.csv y (con --videos) el video anotado en outputs/<secuencia>/.
    """
    reales = conteo_real(cfg)
    seqs = secuencias(cfg, split)
    combos = [(m, l) for m in matches for l in lineas]
    filas, totales = [], {c: 0 for c in combos}
    m_cfg = float(cfg["conteo"]["match_thresh"])
    for seq in seqs:
        cuadros = str(dir_datos(cfg) / seq / "images")
        dets, info = detectar_fuente(cfg, cuadros=cuadros, pesos=pesos, oraculo=oraculo)
        real = int(reales[seq])
        for m in matches:
            if m == m_cfg:  # deja las salidas de la configuración vigente para el análisis de casos
                r = contar(cfg, cuadros=cuadros, pesos=pesos, lineas=lineas, oraculo=oraculo, nombre=seq,
                           con_video=videos, detecciones=(dets, info))
                conteos = {float(k): v for k, v in r["conteos"].items()}
            else:
                registros, _ = seguir(cfg, dets, m)
                conteos = {l: len(contar_cruces(registros, int(round(info["alto"] * l)))) for l in lineas}
            for l in lineas:
                n = conteos[l]
                totales[(m, l)] += n
                filas.append(dict(split=split, secuencia=seq, match_thresh=m, linea=f"{l:.2f}", reales=real,
                                  contados=n, error_abs=abs(n - real), error_rel=round(abs(n - real) / real, 4)))
    total_real = sum(int(reales[s]) for s in seqs)
    resumen = {}
    for (m, l), n in totales.items():
        e = abs(n - total_real)
        resumen[(m, l)] = dict(match_thresh=m, linea=l, reales=total_real, contados=n, error_abs=e,
                               error_rel=round(e / total_real, 4))
        filas.append(dict(split=split, secuencia="TOTAL", match_thresh=m, linea=f"{l:.2f}", reales=total_real,
                          contados=n, error_abs=e, error_rel=round(e / total_real, 4)))
    return {"filas": filas, "total": resumen}


def imprimir_tabla(filas: list[dict]) -> None:
    print(f"\n  {'Secuencia':<10} {'match':>6} {'Línea':>6} {'Reales':>7} {'Contados':>9} {'Err abs':>8} {'Err rel':>8}")
    for f in filas:
        print(f"  {f['secuencia']:<10} {f['match_thresh']:>6} {f['linea']:>6} {f['reales']:>7} {f['contados']:>9} "
              f"{f['error_abs']:>8} {100 * f['error_rel']:>7.1f}%")


def main() -> None:
    p = argparse.ArgumentParser(description="Criterio de éxito (detector + conteo).")
    p.add_argument("--config", default=None)
    p.add_argument("--pesos", default=None, help="por defecto weights/best.pt")
    p.add_argument("--split", choices=["val", "test"], default="test")
    p.add_argument("--lineas", type=float, nargs="+", default=None,
                   help="por defecto: candidatas en val, la de config en test")
    p.add_argument("--match", type=float, nargs="+", default=None,
                   help="match_thresh de ByteTrack; por defecto: candidatos en val, el de config en test")
    p.add_argument("--oraculo", action="store_true", help="contar con las cajas etiquetadas (sin detector)")
    p.add_argument("--videos", action="store_true", help="escribir también los videos anotados")
    a = p.parse_args()

    cfg = cargar_config(a.config)
    c, k = cfg["criterio"], cfg["conteo"]
    pesos = Path(a.pesos).resolve() if a.pesos else ruta_abs(cfg["rutas"]["pesos"]) / "best.pt"
    if not a.oraculo and not pesos.exists():
        raise SystemExit(f"[ERROR] No se encontraron los pesos '{pesos}'. Ejecute antes src/grilla.py.")
    en_val = a.split == "val"
    lineas = [float(x) for x in (a.lineas or (k["lineas_candidatas"] if en_val else [k["linea"]]))]
    matches = [float(x) for x in (a.match or (k["match_thresh_candidatos"] if en_val else [k["match_thresh"]]))]

    conteo = tabla_conteo(cfg, a.split, lineas, matches, pesos, a.oraculo, a.videos)
    print("=" * 74)
    print(f"  CONTEO en {a.split.upper()}" + ("  [ORÁCULO: cajas etiquetadas]" if a.oraculo else ""))
    imprimir_tabla(conteo["filas"])

    resultado = {"split": a.split, "oraculo": a.oraculo, "pesos": None if a.oraculo else relativa(pesos),
                 "conteo": list(conteo["total"].values()), "umbrales": c}
    if en_val:
        # Menor error absoluto total; si empatan, la más cercana a los valores por defecto (línea 0.50, match 0.8).
        m, l = min(conteo["total"], key=lambda ml: (conteo["total"][ml]["error_abs"], abs(ml[1] - 0.5), abs(ml[0] - 0.8)))
        resultado["recomendado"] = {"linea": l, "match_thresh": m}
        print(f"\n  Menor error en validación: línea {l:.2f}, match_thresh {m}")
        print("  Fijarlos en configs/config.yaml (conteo.linea y conteo.match_thresh) ANTES de usar test.")
    elif not a.oraculo:
        clave = (matches[0], lineas[0])
        t = conteo["total"][clave]
        val = evaluar(cfg, pesos, "val", guardar=False)
        previa = val["map50"] >= float(c["map50_val_min"])
        principal = t["error_rel"] <= float(c["error_relativo_max"])
        resultado.update(map50_val=val["map50"], linea=clave[1], match_thresh=clave[0], cumple_previa=previa,
                         cumple_principal=principal, cumple=previa and principal)
        print("\n  CRITERIO DE ÉXITO")
        print(f"  Condición previa  : mAP@0.5 val = {val['map50']:.4f} (>= {c['map50_val_min']}) "
              f"-> {'CUMPLE' if previa else 'NO CUMPLE'}")
        print(f"  Criterio principal: error relativo test = {100 * t['error_rel']:.1f}% "
              f"({t['contados']} contados / {t['reales']} reales) (<= {100 * c['error_relativo_max']:.0f}%) "
              f"-> {'CUMPLE' if principal else 'NO CUMPLE'}")
        print(f"  Veredicto         : {'EL SISTEMA CUMPLE' if previa and principal else 'EL SISTEMA NO CUMPLE'}")
    print("=" * 74)

    logs = ruta_abs(cfg["rutas"]["logs"])
    logs.mkdir(parents=True, exist_ok=True)
    sufijo = f"{a.split}{'_oraculo' if a.oraculo else ''}"
    with open(logs / f"conteo_{sufijo}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(conteo["filas"][0]))
        w.writeheader()
        w.writerows(conteo["filas"])
    (logs / f"criterio_{sufijo}.json").write_text(json.dumps(resultado, indent=2, default=str), encoding="utf-8")
    print(f"[OK] Guardado en {logs / f'criterio_{sufijo}.json'}")


if __name__ == "__main__":
    main()
