"""Entrena UNA configuración del detector YOLO11 con los parámetros fijos de configs/config.yaml.

La grilla completa la ejecuta src/grilla.py, que llama a esta función 8 veces.

Uso:
    uv run python src/entrenar.py --modelo yolo11n.pt --imgsz 640 --lr0 0.01 --nombre prueba --epocas 1
"""
import argparse
from pathlib import Path

from comun import cargar_config, dispositivo, escribir_data_yaml, fijar_semilla, ir_a_raiz, ruta_abs


def entrenar(cfg: dict, modelo: str, imgsz: int, lr0: float, nombre: str, epocas: int | None = None) -> dict:
    """Entrena y devuelve {'pesos': ruta a best.pt, 'carpeta': carpeta de la corrida, 'epocas': hechas}."""
    from ultralytics import YOLO

    ir_a_raiz()
    semilla = int(cfg["proyecto"]["semilla"])
    fijar_semilla(semilla)
    ent = cfg["entrenamiento"]
    disp = dispositivo(cfg)
    epocas = int(epocas if epocas is not None else ent["epocas"])
    print(f"[INFO] {nombre}: {modelo} | imgsz {imgsz} | lr0 {lr0} | {epocas} épocas | dispositivo {disp}")

    yolo = YOLO(modelo)
    yolo.train(
        data=str(escribir_data_yaml(cfg)),
        epochs=epocas,
        patience=int(ent["paciencia"]),
        batch=int(ent["lote"]),
        imgsz=int(imgsz),
        lr0=float(lr0),
        optimizer=ent["optimizador"],
        workers=int(ent["workers"]),
        cache=ent["cache"],
        seed=semilla,
        deterministic=True,
        device=disp,
        project=str(ruta_abs(cfg["rutas"]["logs"])),
        name=nombre,
        exist_ok=True,
        plots=False,  # los gráficos de Ultralytics incluyen cuadros del dataset (datos privados)
        verbose=True,
    )
    carpeta = Path(yolo.trainer.save_dir)
    pesos = carpeta / "weights" / "best.pt"
    if not pesos.exists():
        raise SystemExit(f"[ERROR] El entrenamiento no produjo {pesos}")
    return {"pesos": pesos, "carpeta": carpeta, "epocas": int(yolo.trainer.epoch) + 1}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Entrena una configuración del detector.")
    p.add_argument("--config", default=None, help="config.yaml (por defecto configs/config.yaml)")
    p.add_argument("--modelo", default="yolo11n.pt")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--lr0", type=float, default=0.01)
    p.add_argument("--nombre", default="entrenamiento")
    p.add_argument("--epocas", type=int, default=None, help="sobrescribe las épocas (p. ej. 1 para probar)")
    a = p.parse_args()
    r = entrenar(cargar_config(a.config), a.modelo, a.imgsz, a.lr0, a.nombre, a.epocas)
    print(f"[OK] Pesos: {r['pesos']} ({r['epocas']} épocas)")
