"""Experimentos cortos para elegir el detector YOLO26: 2 modelos x 2 versiones de datos = 4 corridas.

Entrena cada combinación de configs/config.yaml (sección experimentos), la evalúa en validación
y la compara con el YOLO11 base. Si se corta, se vuelve a ejecutar el mismo comando: las corridas
que ya terminaron no se repiten.

Uso:
    uv run python src/entrenamiento/experimentos.py
    uv run python src/entrenamiento/experimentos.py --epocas 1     # prueba de humo (siempre reentrena)
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/, donde está comun.py
sys.path.insert(0, str(Path(__file__).resolve().parent))      # esta carpeta: entrenar.py y evaluar.py

from comun import cargar_config, ruta_abs  # noqa: E402
from entrenar import entrenar  # noqa: E402
from evaluar import evaluar  # noqa: E402

CAMPOS = ["modelo", "datos", "epocas_hechas", "map50", "map50_95", "precision", "recall"]


def fila(modelo: str, datos: str, epocas_hechas: int | str, r: dict) -> dict:
    return {"modelo": modelo, "datos": datos, "epocas_hechas": epocas_hechas, **{k: r[k] for k in CAMPOS[3:]}}


def correr(cfg: dict, epocas: int | None = None) -> list[dict]:
    """Entrena y evalúa (en val) cada modelo x datos. La primera fila es el YOLO11 base."""
    e = cfg["experimentos"]
    carpeta_resultados = ruta_abs(cfg["rutas"]["resultados"])
    # guardar=False: si no, se pisaría resultados/evaluacion_val_best.json (la referencia de YOLO11)
    base = evaluar(cfg, ruta_abs("weights/best.pt"), "val", guardar=False)
    filas = [fila("yolo11n (base)", "lab15 (split antiguo)", "-", base)]

    for modelo in e["modelos"]:
        for datos in e["datos"]:
            nombre = f"exp_{Path(modelo).stem}_{datos}"
            pesos = carpeta_resultados / nombre / "weights" / "best.pt"
            if epocas is not None or not pesos.exists():
                pesos = entrenar(cfg, modelo, e["imgsz"], e["lr0"], nombre, epocas or e["epocas"], datos, e["paciencia"])["pesos"]
            else:
                print(f"[INFO] {nombre}: ya entrenado, se reutiliza {pesos}")
            r = evaluar(cfg, pesos, "val", guardar=False)
            lineas = (carpeta_resultados / nombre / "results.csv").read_text(encoding="utf-8").strip().splitlines()
            filas.append(fila(modelo, datos, len(lineas) - 1, r))  # sin contar el encabezado
    return filas


def elegir(filas: list[dict], empate: float) -> dict:
    """Gana el mayor map50 entre los YOLO26; si otro 'n' queda a menos de `empate`, gana el 'n'
    (más rápido). Entre dos 'n' empatados gana el de mayor map50."""
    yolo26 = [f for f in filas if f["modelo"].startswith("yolo26")]
    mejor = max(yolo26, key=lambda f: f["map50"])
    cercanos_n = [f for f in yolo26 if "yolo26n" in f["modelo"] and mejor["map50"] - f["map50"] < empate]
    return max(cercanos_n, key=lambda f: f["map50"]) if cercanos_n else mejor


def guardar(cfg: dict, filas: list[dict], ganador: dict) -> None:
    carpeta = ruta_abs(cfg["rutas"]["resultados"])
    (carpeta / "tablas").mkdir(parents=True, exist_ok=True)
    with open(carpeta / "experimentos_yolo26.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)

    empate = cfg["experimentos"]["empate_map50"]
    md = ["# Experimentos YOLO26 (val)", "", "| " + " | ".join(CAMPOS) + " |", "|" + "---|" * len(CAMPOS)]
    for f in filas:
        celdas = [f"{f[c]:.4f}" if isinstance(f[c], float) else str(f[c]) for c in CAMPOS]
        md.append("| " + " | ".join(celdas) + " |")
    md += [
        "",
        f"Regla: gana el mayor mAP@50 entre los YOLO26; si el modelo n queda a menos de {empate} del mejor, gana el n.",
        "",
        f"Ganador: {ganador['modelo']} con {ganador['datos']}",
        "",
    ]
    (carpeta / "tablas" / "experimentos_yolo26.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Experimentos cortos YOLO26.")
    p.add_argument("--config", default=None)
    p.add_argument("--epocas", type=int, default=None, help="sobrescribe las épocas (p. ej. 1 para probar)")
    a = p.parse_args()
    cfg = cargar_config(a.config)
    filas = correr(cfg, a.epocas)
    ganador = elegir(filas, cfg["experimentos"]["empate_map50"])
    guardar(cfg, filas, ganador)
    for f in filas:
        print(f)
    print(f"[OK] Ganador: {ganador['modelo']} con {ganador['datos']}")
