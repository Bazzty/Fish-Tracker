"""Detector por cuadro. Solo cambia el archivo de pesos entre YOLO11 y YOLO26 (perfil.detector.pesos)."""
import numpy as np

from comun import dispositivo, imgsz_de_pesos, ir_a_raiz, ruta_abs


class Detector:
    def __init__(self, cfg: dict, perfil: dict):
        from ultralytics import YOLO

        ir_a_raiz()
        d = perfil["detector"]
        pesos = ruta_abs(d["pesos"])
        if not pesos.exists():
            raise FileNotFoundError(f"No se encontraron los pesos del detector: {pesos}")
        self.pesos = pesos
        self.conf, self.iou = float(d["conf"]), float(d["iou"])
        self.imgsz = imgsz_de_pesos(pesos)
        self.disp = dispositivo(cfg)
        self.yolo = YOLO(str(pesos))

    def cajas(self, img: np.ndarray):
        """Objeto Boxes de Ultralytics (en CPU); es lo que consume el tracker."""
        return self.yolo.predict(img, imgsz=self.imgsz, conf=self.conf, iou=self.iou,
                                 device=self.disp, verbose=False)[0].boxes.cpu().numpy()

    def detectar(self, img: np.ndarray) -> list[dict]:
        """Detecciones del cuadro: [{x1, y1, x2, y2, conf}] en píxeles."""
        return [dict(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2), conf=float(c))
                for x1, y1, x2, y2, c in self.cajas(img).data[:, :5].tolist()]
