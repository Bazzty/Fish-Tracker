"""Búsqueda en grilla completa: 8 corridas (modelo x imgsz x lr0) + línea base de COCO.

Cada corrida se entrena solo con train y se evalúa en validación (seq_0002) con los mismos
umbrales. El test no se usa aquí. Se puede interrumpir y relanzar: las corridas ya
registradas en logs/grilla.csv se saltan.

Selección (fijada antes de ver resultados): mayor mAP@0.5 en validación; si otras quedan a
menos de 'empate_map50', gana la más simple (n antes que s, 640 antes que 960).
La elegida se copia a weights/best.pt con su ficha en weights/best.yaml.

Uso:
    uv run python src/grilla.py                      # línea base + 8 corridas + selección
    uv run python src/grilla.py --solo R1 R2         # algunas corridas
    uv run python src/grilla.py --epocas 1 --solo R1 # prueba rápida (no usar para la entrega)
    uv run python src/grilla.py --seleccionar        # solo recalcula la selección
"""
import argparse
import csv
import itertools
import shutil
import time
from pathlib import Path

import yaml

from comun import RAIZ, cargar_config, relativa, ruta_abs, sha256
from entrenar import entrenar
from evaluar import evaluar

COLUMNAS = ["corrida", "modelo", "imgsz", "lr0", "epocas", "map50", "map50_95", "precision", "recall",
            "minutos", "pesos"]


def corridas(cfg: dict) -> list[dict]:
    """R1..R8 en orden modelo, imgsz, lr0. Se ejecutan primero las de imagen 640 (más rápidas)."""
    g = cfg["grilla"]
    todas = [dict(corrida=f"R{i}", modelo=m, imgsz=int(s), lr0=float(l))
             for i, (m, s, l) in enumerate(itertools.product(g["modelos"], g["imgsz"], g["lr0"]), start=1)]
    return sorted(todas, key=lambda c: (c["imgsz"], int(c["corrida"][1:])))


def leer_tabla(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def agregar_fila(ruta: Path, fila: dict) -> None:
    nueva = not ruta.exists()
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nueva:
            w.writeheader()
        w.writerow(fila)


def linea_base(cfg: dict, logs: Path) -> None:
    ruta = logs / "linea_base.csv"
    filas = []
    for m in cfg["grilla"]["linea_base"]:
        r = evaluar(cfg, m, "val", imgsz=640, guardar=False)
        filas.append(dict(modelo=m, imgsz=640, map50=round(r["map50"], 4), map50_95=round(r["map50_95"], 4),
                          precision=round(r["precision"], 4), recall=round(r["recall"], 4)))
        print(f"[BASE] {m}: mAP@0.5 val = {r['map50']:.4f}")
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def simplicidad(fila: dict, cfg: dict) -> tuple:
    g = cfg["grilla"]
    return (g["modelos"].index(fila["modelo"]), int(fila["imgsz"]))


def seleccionar(cfg: dict, logs: Path) -> dict | None:
    tabla = leer_tabla(logs / "grilla.csv")
    if not tabla:
        print("[AVISO] No hay corridas en logs/grilla.csv.")
        return None
    mejor = max(float(f["map50"]) for f in tabla)
    empate = float(cfg["grilla"]["empate_map50"])
    candidatas = [f for f in tabla if mejor - float(f["map50"]) < empate]
    elegida = min(candidatas, key=lambda f: (*simplicidad(f, cfg), -float(f["map50"])))

    # Efecto de cada factor: promedio de mAP@0.5 de las corridas con cada nivel.
    efectos = []
    for factor in ("modelo", "imgsz", "lr0"):
        for nivel in sorted({f[factor] for f in tabla}):
            v = [float(f["map50"]) for f in tabla if f[factor] == nivel]
            efectos.append(dict(factor=factor, nivel=nivel, corridas=len(v), map50_promedio=round(sum(v) / len(v), 4)))
    with open(logs / "efectos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(efectos[0]))
        w.writeheader()
        w.writerows(efectos)

    origen = Path(elegida["pesos"])
    origen = origen if origen.is_absolute() else RAIZ / origen
    destino = ruta_abs(cfg["rutas"]["pesos"]) / "best.pt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    ficha = {
        "corrida": elegida["corrida"], "modelo": elegida["modelo"], "imgsz": int(elegida["imgsz"]),
        "lr0": float(elegida["lr0"]), "epocas": int(elegida["epocas"]),
        "map50_val": float(elegida["map50"]), "map50_95_val": float(elegida["map50_95"]),
        "corridas_en_empate": [f["corrida"] for f in candidatas],
        "corridas_registradas": len(tabla),
        "origen": elegida["pesos"], "sha256": sha256(destino),
    }
    with open(destino.with_suffix(".yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(ficha, f, allow_unicode=True, sort_keys=False)
    print(f"[ELEGIDA] {ficha['corrida']} ({ficha['modelo']}, {ficha['imgsz']}, lr0 {ficha['lr0']}) "
          f"mAP@0.5 val {ficha['map50_val']:.4f} -> {destino}")
    if len(tabla) < len(corridas(cfg)):
        print(f"[AVISO] Selección con {len(tabla)} de {len(corridas(cfg))} corridas.")
    return ficha


def curvas(logs: Path, tabla: list[dict]) -> None:
    """Pérdida de validación y mAP@0.5 por época de cada corrida (desde results.csv, sin imágenes del dataset)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ejes = plt.subplots(1, 2, figsize=(12, 4.5))
    for f in tabla:
        res = logs / f["corrida"] / "results.csv"
        if not res.exists():
            continue
        with open(res, newline="", encoding="utf-8") as fh:
            filas = [{k.strip(): v for k, v in r.items()} for r in csv.DictReader(fh)]
        ep = [int(float(r["epoch"])) for r in filas]
        et = f"{f['corrida']} {Path(f['modelo']).stem[-1]} {f['imgsz']} {f['lr0']}"
        ejes[0].plot(ep, [float(r["val/box_loss"]) for r in filas], label=et)
        ejes[1].plot(ep, [float(r["metrics/mAP50(B)"]) for r in filas], label=et)
    ejes[0].set(title="Pérdida de caja en validación", xlabel="época")
    ejes[1].set(title="mAP@0.5 en validación", xlabel="época", ylim=(0, 1))
    ejes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(logs / "curvas.png", dpi=120)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description="Grilla de 8 corridas y selección en validación.")
    p.add_argument("--config", default=None)
    p.add_argument("--solo", nargs="+", default=None, help="corridas a ejecutar, p. ej. R1 R5")
    p.add_argument("--epocas", type=int, default=None, help="sobrescribe épocas (solo para probar)")
    p.add_argument("--sin-base", action="store_true", help="no evaluar la línea base de COCO")
    p.add_argument("--seleccionar", action="store_true", help="no entrenar: solo seleccionar y resumir")
    p.add_argument("--rehacer", action="store_true", help="vuelve a entrenar corridas ya registradas")
    a = p.parse_args()

    cfg = cargar_config(a.config)
    if a.epocas is not None:  # prueba: todo va a logs/prueba/ y nunca toca weights/best.pt
        cfg["rutas"]["logs"] = cfg["rutas"]["pesos"] = str(Path(cfg["rutas"]["logs"]) / "prueba")
    logs = ruta_abs(cfg["rutas"]["logs"])
    logs.mkdir(parents=True, exist_ok=True)
    tabla_ruta = logs / "grilla.csv"

    if not a.seleccionar:
        if a.epocas is not None:
            print(f"[AVISO] Épocas sobrescritas a {a.epocas}: resultados de prueba en {logs}")
        if not a.sin_base and not (logs / "linea_base.csv").exists():
            linea_base(cfg, logs)
        hechas = {f["corrida"] for f in leer_tabla(tabla_ruta)}
        for c in corridas(cfg):
            if a.solo and c["corrida"] not in a.solo:
                continue
            if c["corrida"] in hechas and not a.rehacer:
                print(f"[SALTA] {c['corrida']} ya está en {tabla_ruta.name}")
                continue
            if c["corrida"] in hechas:  # rehacer: se quita la fila anterior
                filas = [f for f in leer_tabla(tabla_ruta) if f["corrida"] != c["corrida"]]
                tabla_ruta.unlink()
                for f in filas:
                    agregar_fila(tabla_ruta, f)
            t0 = time.time()
            r = entrenar(cfg, c["modelo"], c["imgsz"], c["lr0"], c["corrida"], a.epocas)
            ev = evaluar(cfg, r["pesos"], "val", imgsz=c["imgsz"], guardar=False)
            fila = dict(**c, epocas=r["epocas"], map50=round(ev["map50"], 4), map50_95=round(ev["map50_95"], 4),
                        precision=round(ev["precision"], 4), recall=round(ev["recall"], 4),
                        minutos=round((time.time() - t0) / 60, 1),
                        pesos=relativa(r["pesos"]))
            agregar_fila(tabla_ruta, fila)
            print(f"[OK] {c['corrida']}: mAP@0.5 val = {fila['map50']:.4f} en {fila['minutos']} min")

    tabla = leer_tabla(tabla_ruta)
    if tabla:
        curvas(logs, tabla)
    seleccionar(cfg, logs)


if __name__ == "__main__":
    main()
