"""Evalúa el detector (mAP@0.5, mAP@0.5:0.95, precisión y recall) en validación o en test.

Usa el mismo tamaño de imagen con que se entrenaron los pesos y los umbrales fijos de la
configuración, para que el mAP sea reproducible. Evalúa sin distinguir clase (single_cls):
no cambia nada en el modelo entrenado (una sola clase) y permite evaluar la línea base de COCO.

Uso:
    uv run python src/entrenamiento/evaluar.py                     # weights/yolo26.pt en test
    uv run python src/entrenamiento/evaluar.py --split val
    uv run python src/entrenamiento/evaluar.py --pesos yolo26n.pt --split val    # pesos de COCO, sin entrenar
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/, donde está comun.py

from comun import (  # noqa: E402
    RAIZ, cargar_config, dispositivo, escribir_data_yaml, imgsz_de_pesos, ir_a_raiz, relativa, ruta_abs, sha256,
)


def evaluar(cfg: dict, pesos: str | Path, split: str = "test", imgsz: int | None = None, guardar: bool = True) -> dict:
    from ultralytics import YOLO

    ir_a_raiz()
    pesos = Path(pesos)
    es_base = not pesos.exists() and pesos.parent == Path(".")  # yolo26n.pt de COCO: Ultralytics lo descarga
    if not pesos.exists() and not es_base:
        raise SystemExit(f"[ERROR] No se encontraron los pesos '{pesos}'. Entrene antes con src/entrenamiento/entrenar.py.")
    yolo = YOLO(str(pesos))
    if imgsz is None:
        imgsz = imgsz_de_pesos(Path(yolo.ckpt_path)) if getattr(yolo, "ckpt_path", None) else 640
    ev = cfg["evaluacion"]
    r = yolo.val(
        data=str(escribir_data_yaml(cfg)),
        split=split,
        imgsz=int(imgsz),
        batch=int(ev["lote"]),
        conf=float(ev["conf"]),
        iou=float(ev["iou"]),
        single_cls=True,
        device=dispositivo(cfg),
        plots=False,
        project=str(RAIZ / "runs" / "val"),
        name=split,
        exist_ok=True,
        verbose=False,
    )
    res = {
        "pesos": relativa(pesos),
        "sha256": sha256(Path(yolo.ckpt_path)) if getattr(yolo, "ckpt_path", None) else None,
        "split": split,
        "imgsz": int(imgsz),
        "map50": float(r.box.map50),
        "map50_95": float(r.box.map),
        "precision": float(r.box.mp),
        "recall": float(r.box.mr),
    }
    if guardar:
        salida = ruta_abs(cfg["rutas"]["resultados"]) / f"evaluacion_{split}_{pesos.stem}.json"
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json.dumps(res, indent=2), encoding="utf-8")
        res["archivo"] = str(salida)
    return res


def imprimir(res: dict) -> None:
    print("\n" + "=" * 60)
    print(f"  Detector en {res['split'].upper()} | pesos {res['pesos']} | imgsz {res['imgsz']}")
    print("=" * 60)
    print(f"  mAP@0.5      : {res['map50']:.4f}")
    print(f"  mAP@0.5:0.95 : {res['map50_95']:.4f}")
    print(f"  Precisión    : {res['precision']:.4f}")
    print(f"  Recall       : {res['recall']:.4f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Evaluación del detector.")
    p.add_argument("--config", default=None)
    p.add_argument("--pesos", default=None, help="por defecto weights/yolo26.pt")
    p.add_argument("--split", choices=["val", "test"], default="test")
    p.add_argument("--imgsz", type=int, default=None, help="por defecto, el de entrenamiento de los pesos")
    a = p.parse_args()
    cfg = cargar_config(a.config)
    pesos = a.pesos or ruta_abs(cfg["rutas"]["pesos"]) / "yolo26.pt"
    if a.pesos and Path(a.pesos).exists():
        pesos = Path(a.pesos).resolve()  # relativa a la carpeta desde donde se ejecuta
    res = evaluar(cfg, pesos, a.split, a.imgsz)
    imprimir(res)
    print(f"[OK] Guardado en {res['archivo']}")
