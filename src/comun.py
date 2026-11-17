"""Utilidades compartidas: rutas, configuración, semilla, dispositivo y lectura de secuencias.

Todas las rutas se resuelven desde la raíz del repositorio, así los scripts
funcionan sin importar desde qué carpeta se ejecuten.
"""
import hashlib
import os
import random
import re
from pathlib import Path

import numpy as np
import yaml

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "configs" / "config.yaml"
EXT_IMAGEN = (".jpg", ".jpeg", ".png")
NUM_CUADRO = re.compile(r"(\d+)(?=\.[^.]+$)")  # último número antes de la extensión


def leer_yaml(ruta: Path) -> dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_config(ruta: str | Path | None = None) -> dict:
    """Sin ruta: configs/config.yaml. Una ruta dada se busca desde la carpeta actual y, si no, desde la raíz."""
    if not ruta:
        return leer_yaml(CONFIG)
    return leer_yaml(Path(ruta).resolve() if Path(ruta).exists() else ruta_abs(ruta))


def ruta_abs(ruta: str | Path) -> Path:
    """Ruta relativa a la raíz del repositorio (o la misma si ya es absoluta)."""
    p = Path(ruta)
    return p if p.is_absolute() else RAIZ / p


def relativa(ruta: Path) -> str:
    """Ruta relativa a la raíz si está dentro del repositorio (así la tabla sirve en otra máquina)."""
    try:
        return ruta.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return ruta.resolve().as_posix()


def ir_a_raiz() -> None:
    """Fija el directorio de trabajo en la raíz: Ultralytics descarga ahí los pesos base."""
    os.chdir(RAIZ)


def fijar_semilla(semilla: int) -> None:
    import torch

    random.seed(semilla)
    np.random.seed(semilla)
    torch.manual_seed(semilla)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(semilla)


def dispositivo(cfg: dict):
    """'auto': GPU 0 si hay CUDA; si no, MPS (Mac) o CPU. Falla si la GPU no es compatible con este PyTorch."""
    import torch

    pedido = str(cfg["proyecto"].get("dispositivo", "auto"))
    if pedido != "auto":
        return int(pedido) if pedido.isdigit() else pedido
    if torch.cuda.is_available():
        verificar_gpu()
        return 0
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def verificar_gpu() -> None:
    """Corta con un mensaje claro si PyTorch no trae kernels para la GPU (p. ej. RTX 50 con CUDA < 12.8)."""
    import torch

    mayor, menor = torch.cuda.get_device_capability(0)
    arq = f"sm_{mayor}{menor}"
    soportadas = torch.cuda.get_arch_list()
    if arq not in soportadas:
        raise SystemExit(
            f"[ERROR] La GPU {torch.cuda.get_device_name(0)} ({arq}) no está soportada por "
            f"torch {torch.__version__} (soporta {soportadas}). Instale torch con CUDA 12.8+: uv sync"
        )


def leer_split(cfg: dict) -> dict:
    return leer_yaml(ruta_abs(cfg["rutas"]["split"]))


def secuencias(cfg: dict, conjunto: str) -> list[str]:
    split = leer_split(cfg)
    if conjunto not in split:
        raise SystemExit(f"[ERROR] Conjunto '{conjunto}' no existe en {cfg['rutas']['split']}")
    return list(split[conjunto])


def conteo_real(cfg: dict) -> dict:
    return leer_yaml(ruta_abs(cfg["rutas"]["conteo_real"]))["conteo_real"]


def dir_datos(cfg: dict) -> Path:
    return ruta_abs(cfg["rutas"]["datos"])


def escribir_data_yaml(cfg: dict, version: str | None = None) -> Path:
    """Genera el data.yaml de Ultralytics desde configs/split.yaml con ruta absoluta.

    version: None -> runs/data.yaml (train completo, como siempre); 'dat01' -> runs/data_dat01.yaml
    (train sin las lab15_*); 'lab15_dat01' -> runs/data_lab15_dat01.yaml (train completo).
    Val y test son siempre los mismos. Con ruta absoluta Ultralytics no la resuelve contra su carpeta
    global de datasets; as_posix() evita barras invertidas de Windows dentro del YAML.
    """
    if version not in (None, "dat01", "lab15_dat01"):
        raise SystemExit(f"[ERROR] Versión de data.yaml desconocida: {version} (use dat01 o lab15_dat01)")
    datos = dir_datos(cfg)
    split = leer_split(cfg)
    faltan = [s for c in ("train", "val", "test") for s in split[c] if not (datos / s / "images").is_dir()]
    if faltan:
        raise SystemExit(f"[ERROR] Faltan secuencias en {datos}: {faltan}. Ver README, sección Datos.")
    train = [s for s in split["train"] if not (version == "dat01" and s.startswith("lab15_"))]
    contenido = {
        "path": datos.as_posix(),
        "train": [f"{s}/images" for s in train],
        **{c: [f"{s}/images" for s in split[c]] for c in ("val", "test")},
        "names": {0: cfg["proyecto"].get("clase", "fish")},
    }
    salida = RAIZ / "runs" / (f"data_{version}.yaml" if version else "data.yaml")
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        yaml.safe_dump(contenido, f, allow_unicode=True, sort_keys=False)
    return salida


def numero_cuadro(ruta: Path) -> int | None:
    m = NUM_CUADRO.search(ruta.name)
    return int(m.group(1)) if m else None


def listar_cuadros(carpeta: Path) -> list[tuple[int, Path]]:
    """Cuadros de una carpeta ordenados por su número. Ignora archivos ocultos (._ de macOS)."""
    archivos = [
        p for p in carpeta.iterdir()
        if p.suffix.lower() in EXT_IMAGEN and not p.name.startswith(".")
    ]
    if not archivos:
        raise SystemExit(f"[ERROR] No hay imágenes en {carpeta}")
    nums = [numero_cuadro(p) for p in archivos]
    if any(n is None for n in nums):  # sin número: orden alfabético y numeración consecutiva
        return list(enumerate(sorted(archivos)))
    return sorted(zip(nums, archivos))


def leer_etiquetas_xyxy(txt: Path, ancho: int, alto: int) -> np.ndarray:
    """Etiquetas YOLO (clase xc yc w h, normalizadas) a cajas en píxeles [x1, y1, x2, y2]."""
    if not txt.exists():
        return np.zeros((0, 4), dtype=np.float32)
    filas = [l.split() for l in txt.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not filas:
        return np.zeros((0, 4), dtype=np.float32)
    a = np.array([[float(v) for v in f[1:5]] for f in filas], dtype=np.float32)
    xc, yc, w, h = a[:, 0] * ancho, a[:, 1] * alto, a[:, 2] * ancho, a[:, 3] * alto
    return np.stack([xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2], axis=1)


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def imgsz_de_pesos(pesos: Path, por_defecto: int = 640) -> int:
    """Tamaño de imagen con que se entrenaron los pesos (guardado por Ultralytics en el checkpoint)."""
    import torch

    ckpt = torch.load(pesos, map_location="cpu", weights_only=False)
    args = ckpt.get("train_args") or {}
    v = args.get("imgsz", por_defecto)
    return int(v[0] if isinstance(v, (list, tuple)) else v)


class VideoH264:
    """Escribe un .mp4 H.264 (yuv420p) con el FFmpeg de imageio-ffmpeg: se reproduce en cualquier lado.

        video = VideoH264(ruta, ancho, alto, fps); video.escribir(img_bgr); video.cerrar()
    """

    def __init__(self, ruta: Path, ancho: int, alto: int, fps: float):
        import subprocess

        import imageio_ffmpeg

        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-s", f"{ancho}x{alto}", "-r", f"{fps:g}", "-i", "-", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", str(self.ruta)],
            stdin=subprocess.PIPE)

    def escribir(self, img: np.ndarray) -> None:
        self.proc.stdin.write(img.tobytes())

    def cerrar(self) -> None:
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise SystemExit(f"[ERROR] FFmpeg no pudo crear {self.ruta}")
