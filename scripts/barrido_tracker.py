"""Barrido de trackers y umbrales contra DAT-02 (tarea T14): tabla comparativa y decisión.

Genera variantes de los YAML de cada tracker (runs/barrido_tracker/), las evalúa todas con
evaluar-seguimiento sobre las mismas detecciones (con el detector y con oráculo) y las ordena por:
    1. menor error de conteo con el detector (la comparación principal del plan),
    2. mayor IDF1,
    3. menos ID switches.
Escribe resultados/tablas/comparacion_trackers.md y resultados/comparacion_trackers.json (con --yaml test,
comparacion_trackers_test.md y .json, para no pisar la decisión tomada en val); las trayectorias y
métricas de cada configuración quedan en outputs/barrido_tracker/<detector u oraculo>/.
Con --aplicar copia el ganador a configs/tracker_variante.yaml, que es el tracker del perfil variante.
Solo se aplica desde val: elegir el tracker con test lo dejaría sin un conjunto independiente para confirmarlo.

Uso:
    uv run python scripts/barrido_tracker.py                      # val, perfil variante (YOLO26 + histéresis)
    uv run python scripts/barrido_tracker.py --yaml test          # las secuencias de test de configs/split.yaml
    uv run python scripts/barrido_tracker.py --rapido             # sin DeepSORT ni BoT-SORT+ReID (más lentos)
    uv run python scripts/barrido_tracker.py --aplicar            # y deja el ganador en el perfil variante
"""
import argparse
import itertools
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml  # noqa: E402

from comun import RAIZ, cargar_config, leer_yaml, relativa, ruta_abs, secuencias  # noqa: E402
from tracker.evaluar_seguimiento import con_gt, evaluar  # noqa: E402
from tracker.pipeline import cargar_perfil  # noqa: E402
from tracker.salidas import carpeta, con_conteo, nombre_detector, nombre_regla  # noqa: E402

# Valores a probar sobre el YAML base de cada tracker (el resto de los parámetros queda igual).
GRILLA = {
    "bytetrack": {"track_buffer": [15, 30], "match_thresh": [0.8, 0.9, 0.95]},
    "botsort": {"track_buffer": [15, 30], "match_thresh": [0.8, 0.9, 0.95]},
    "botsort_reid": {"track_buffer": [15, 30]},
    "ocsort": {"lost_track_buffer": [15, 30, 60], "minimum_iou_threshold": [0.1, 0.2],
               "minimum_consecutive_frames": [1, 3]},
    "deepsort": {"max_age": [15, 30]},
}
# Por qué estos valores (diagnóstico de seq_00046): a 10 fps un pez baja 56-117 px por cuadro y la caja de un cuadro
# apenas se superpone con la del siguiente (IoU 0.15-0.35), así que se prueban umbrales de asociación más permisivos
# (match_thresh alto, IoU mínimo bajo), confirmar IDs nuevos de inmediato y búferes cortos (un pez cruza en 1-2 s).
LENTOS = ("botsort_reid", "deepsort")
ABREV = {"track_buffer": "buf", "lost_track_buffer": "buf", "max_age": "buf",
         "match_thresh": "mt", "minimum_iou_threshold": "iou", "minimum_consecutive_frames": "min"}
CARPETA = RAIZ / "runs" / "barrido_tracker"


def generar(rapido: bool) -> dict[str, dict]:
    """Escribe un YAML por combinación y devuelve {nombre: {base, cambios, ruta}}."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    variantes = {}
    for base, grilla in GRILLA.items():
        if rapido and base in LENTOS:
            continue
        original = leer_yaml(ruta_abs(f"configs/{base}.yaml"))
        claves = list(grilla)
        for valores in itertools.product(*grilla.values()):
            cambios = dict(zip(claves, valores))
            nombre = base + "_" + "_".join(f"{ABREV[k]}{v}" for k, v in cambios.items())
            ruta = CARPETA / f"{nombre}.yaml"
            texto = yaml.safe_dump({**original, **cambios}, sort_keys=False, allow_unicode=True)
            ruta.write_text(f"# Generado por scripts/barrido_tracker.py desde configs/{base}.yaml: {cambios}\n" + texto,
                            encoding="utf-8")
            variantes[nombre] = dict(base=base, cambios=cambios, ruta=ruta)
    return variantes


def totales(filas: list[dict]) -> dict[str, dict]:
    return {r["tracker"]: r for r in filas if r["secuencia"] == "TOTAL"}


def tabla(variantes: dict, res: dict[str, dict], orden: list[str]) -> list[str]:
    t = ["| # | Configuración | Parámetros | IDF1 | IDSW | MOTA | FP | FN | Conteo | Referencia | Error |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, n in enumerate(orden, 1):
        r = res[n]
        params = ", ".join(f"{k}={v}" for k, v in variantes[n]["cambios"].items())
        t.append(f"| {i} | `{n}` | {params} | {100 * r['IDF1']:.1f} % | {r['IDSW']} | {100 * r['MOTA']:.1f} % | "
                 f"{r['FP']} | {r['FN']} | {r['conteo_tracker']} | {r['conteo_referencia']} | **{r['error_conteo']}** |")
    return t


p = argparse.ArgumentParser()
p.add_argument("--yaml", "--conjunto", dest="conjunto", choices=["val", "test"], default="val",
               help="conjunto de configs/split.yaml que se evalúa (por defecto val)")
p.add_argument("--seq", nargs="+", help="secuencias concretas (en vez de --yaml)")
p.add_argument("--perfil", default="variante", help="detector y regla de conteo (por defecto YOLO26 + histéresis)")
p.add_argument("--conteo", choices=["linea_simple", "dos_lineas"], help="regla de conteo (por defecto la del perfil)")
p.add_argument("--rapido", action="store_true", help="sin DeepSORT ni BoT-SORT+ReID")
p.add_argument("--sin-oraculo", action="store_true", help="solo con el detector (más rápido)")
p.add_argument("--aplicar", action="store_true", help="copiar el ganador a configs/tracker_variante.yaml")
p.add_argument("--config", default=None)
a = p.parse_args()

if a.aplicar and (a.conjunto != "val" or a.seq):
    sys.exit("[ERROR] --aplicar solo se usa con val: test sirve para confirmar el ganador, no para elegirlo")
cfg = cargar_config(a.config)
perfil = con_conteo(cargar_perfil(a.perfil), a.conteo)
disponibles = con_gt(cfg)
seqs = a.seq or [s for s in secuencias(cfg, a.conjunto) if s in disponibles]
if not seqs:
    sys.exit(f"[ERROR] No hay secuencias de '{a.conjunto}' con gt.txt en {cfg['rutas']['tracking']}")
variantes = generar(a.rapido)
rutas = [str(v["ruta"]) for v in variantes.values()]
print(f"Barrido: {len(variantes)} configuraciones x {len(seqs)} secuencias, perfil {perfil['nombre']}")

grupo = f"{a.conjunto if not a.seq else '_'.join(seqs)}_{nombre_regla(perfil)}"
res = {"detector": totales(evaluar(cfg, perfil, seqs, rutas, carpeta(cfg, "barrido_tracker", nombre_detector(perfil)),
                                   oraculo=False, grupo=grupo))}
if not a.sin_oraculo:
    res["oraculo"] = totales(evaluar(cfg, perfil, seqs, rutas, carpeta(cfg, "barrido_tracker", "oraculo"),
                                     oraculo=True, grupo=grupo))

clave = lambda n: (res["detector"][n]["error_conteo"], -res["detector"][n]["IDF1"], res["detector"][n]["IDSW"])
orden = sorted(variantes, key=clave)
ganador = orden[0]
g = res["detector"][ganador]
regla = perfil.get("conteo", {}).get("tipo", "linea_simple")

conjunto = a.conjunto if not a.seq else "secuencias indicadas"
md = [f"# Comparación de trackers (T14): {conjunto}", "",
      f"Generado por `scripts/barrido_tracker.py` el {datetime.now():%Y-%m-%d %H:%M}. Perfil `{perfil['nombre']}` "
      f"(detector `{perfil['detector']['pesos']}`, conteo `{regla}`), {len(seqs)} secuencias de {conjunto}: "
      f"{', '.join(seqs)}.",
      "", "Criterio: 1) menor error de conteo con el detector, 2) mayor IDF1, 3) menos ID switches. "
      "La referencia es la línea simple aplicada a las trayectorias de DAT-02.", "",
      "## Decisión", "",
      f"**`{ganador}`** ({variantes[ganador]['base']}, "
      f"{', '.join(f'{k}={v}' for k, v in variantes[ganador]['cambios'].items())}): contó {g['conteo_tracker']} "
      f"de {g['conteo_referencia']} peces (error {g['error_conteo']}), IDF1 {100 * g['IDF1']:.1f} %, "
      f"{g['IDSW']} cambios de ID.", "",
      "## Con el detector (resultado real)", "", *tabla(variantes, res["detector"], orden)]
if "oraculo" in res:
    orden_o = sorted(variantes, key=lambda n: (res["oraculo"][n]["error_conteo"], -res["oraculo"][n]["IDF1"]))
    md += ["", "## Con oráculo (cajas del GT: mide solo el tracker)", "", *tabla(variantes, res["oraculo"], orden_o),
           "", "Si un tracker acierta con oráculo y falla con el detector, la falla es del detector, no del tracker."]
sufijo = "" if a.conjunto == "val" and not a.seq else f"_{a.conjunto if not a.seq else '_'.join(seqs)}"
destino = ruta_abs(cfg["rutas"]["resultados"]) / "tablas" / f"comparacion_trackers{sufijo}.md"
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text("\n".join(md) + "\n", encoding="utf-8")
(destino.parent.parent / f"comparacion_trackers{sufijo}.json").write_text(json.dumps({
    "fecha": datetime.now().isoformat(timespec="seconds"), "perfil": perfil["nombre"],
    "pesos": perfil["detector"]["pesos"], "regla_conteo": regla, "secuencias": seqs, "ganador": ganador,
    "configuraciones": {n: {"tracker": v["base"], "cambios": v["cambios"],
                            **{modo: {k: r[n][k] for k in ("IDF1", "IDSW", "MOTA", "FP", "FN", "conteo_tracker",
                                                           "conteo_referencia", "error_conteo")}
                               for modo, r in res.items()}} for n, v in variantes.items()},
}, indent=2, ensure_ascii=False, default=float), encoding="utf-8")

if a.aplicar:
    elegido = ruta_abs("configs/tracker_variante.yaml")
    texto = variantes[ganador]["ruta"].read_text(encoding="utf-8").split("\n", 1)[1]
    elegido.write_text(f"# Tracker del perfil variante. Elegido por scripts/barrido_tracker.py el "
                       f"{datetime.now():%Y-%m-%d} ({ganador}); ver resultados/tablas/comparacion_trackers.md.\n"
                       + texto, encoding="utf-8")

print("=" * 72)
for n in orden[:5]:
    r = res["detector"][n]
    print(f"  {n:32s} error {r['error_conteo']:3d} | IDF1 {r['IDF1']:.1%} | IDSW {r['IDSW']}")
print(f"  Ganador: {ganador}")
print(f"  Tabla: {relativa(destino)}")
if a.aplicar:
    print("  Aplicado en configs/tracker_variante.yaml (perfil variante)")
print("=" * 72)
