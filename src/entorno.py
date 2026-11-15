"""Verifica el entorno antes de entrenar: Python, PyTorch, GPU, Ultralytics, ByteTrack y datos.

Solo cuenta archivos de data/, no abre imágenes ni etiquetas.

Uso: uv run python src/entorno.py
"""
import platform
import sys

from comun import cargar_config, dir_datos, leer_split


def main() -> int:
    import torch

    ok = True
    print(f"Python       : {sys.version.split()[0]} ({platform.system()} {platform.machine()})")
    print(f"PyTorch      : {torch.__version__}")
    if torch.cuda.is_available():
        mayor, menor = torch.cuda.get_device_capability(0)
        arq, soportadas = f"sm_{mayor}{menor}", torch.cuda.get_arch_list()
        compatible = arq in soportadas
        ok &= compatible
        print(f"GPU          : {torch.cuda.get_device_name(0)} ({arq}) | CUDA {torch.version.cuda}")
        print(f"Arquitecturas: {soportadas} -> {'OK' if compatible else 'NO SOPORTA ESTA GPU'}")
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        print("GPU          : Apple MPS (sirve para probar; la grilla se corre en la RTX 5070 Ti)")
    else:
        print("GPU          : no disponible, se usará CPU")

    import ultralytics

    print(f"Ultralytics  : {ultralytics.__version__}")
    try:
        import lap  # noqa: F401  (asignación lineal que usa ByteTrack)

        print("lap          : OK")
    except ImportError:
        ok = False
        print("lap          : FALTA (uv sync)")

    cfg = cargar_config()
    datos = dir_datos(cfg)
    split = leer_split(cfg)
    print(f"Datos        : {datos}")
    for conjunto in ("train", "val", "test"):
        for seq in split[conjunto]:
            img, lab = datos / seq / "images", datos / seq / "labels"
            n_img = sum(1 for p in img.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")) if img.is_dir() else 0
            n_lab = sum(1 for _ in lab.glob("*.txt")) if lab.is_dir() else 0
            estado = "OK" if n_img and n_lab else "FALTA"
            ok &= estado == "OK"
            print(f"  {conjunto:<5} {seq}: {n_img:>4} imágenes, {n_lab:>4} etiquetas  {estado}")
    print("\nEntorno listo." if ok else "\nHay problemas: revisar lo marcado.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
