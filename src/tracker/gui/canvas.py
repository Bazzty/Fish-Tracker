"""Widget que muestra un cuadro del video y permite dibujar y editar tubos (canales).

Cada canal es un rectángulo (formato común: tracker.canales.Canal) con dos líneas de conteo,
A (entrada) y B (salida), dadas como fracción del alto del tubo medida desde arriba.
Los peces avanzan de arriba hacia abajo.

- Dibujar: arrastrar el mouse sobre el video.
- Un tubo en edición muestra 8 manillas (ancho/alto), grips en las líneas A y B, y se mueve
  arrastrándolo por dentro. Un tubo fijo no se modifica.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from tracker.canales import Canal

from . import lineas

PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6", "#bfef45"]
HANDLE_PX = 7  # radio de las manillas (px de pantalla)
LINE_HIT_PX = 6  # tolerancia para agarrar una línea A/B
MIN_SIZE = 5.0  # tamaño mínimo de un tubo (px del video)
MIN_GAP = 0.02  # separación mínima entre A y B (fracción del alto)

# (hx, hy): -1 = borde izq./sup., 1 = borde der./inf., 0 = centro
HANDLES = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]
CURSORS = {
    (-1, -1): Qt.SizeFDiagCursor, (1, 1): Qt.SizeFDiagCursor,
    (1, -1): Qt.SizeBDiagCursor, (-1, 1): Qt.SizeBDiagCursor,
    (0, -1): Qt.SizeVerCursor, (0, 1): Qt.SizeVerCursor,
    (-1, 0): Qt.SizeHorCursor, (1, 0): Qt.SizeHorCursor,
}


def num_de(canal_id: str) -> int:
    """'canal_3' -> 3 (para numerar y colorear de forma estable)."""
    try:
        return int(canal_id.rsplit("_", 1)[-1])
    except ValueError:
        return 1


def color_for(canal_id: str) -> QColor:
    return QColor(PALETTE[(num_de(canal_id) - 1) % len(PALETTE)])


class VideoCanvas(QWidget):
    channel_drawn = Signal(object)  # caja (x1, y1, x2, y2) en px del video
    channel_clicked = Signal(str)  # clic sobre un tubo existente
    channel_edited = Signal(str)  # se movió o redimensionó un tubo / línea
    channel_moving = Signal(str)  # mientras se arrastra (para refrescar el panel en vivo)
    editing_changed = Signal(str)  # id del tubo en edición, o "" si todos están fijos
    drawing_changed = Signal(bool)
    message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self._channels: list[Canal] = []
        self._active_id: str | None = None
        self._editing_id: str | None = None
        self._drawing = False
        self._rect_start: tuple[float, float] | None = None
        self._cursor: QPointF | None = None
        self._drag: dict | None = None
        self._overlay: tuple[list, list] | None = None  # (detecciones, trayectorias) del cuadro en vivo
        self._conteos: dict[str, int] = {}
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    # ---------- API pública ----------
    @property
    def is_drawing(self) -> bool:
        return self._drawing

    @property
    def editing_id(self) -> str | None:
        return self._editing_id

    def set_frame(self, image: QImage) -> None:
        self._image = image
        self.update()

    def set_channels(self, channels: list[Canal]) -> None:
        self._channels = channels
        self.update()

    def set_overlay(self, detecciones: list, trayectorias: list) -> None:
        """Cajas del cuadro que se está procesando (px del video)."""
        self._overlay = (detecciones, trayectorias)
        self.update()

    def clear_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay = None
            self.update()

    def set_conteos(self, conteos: dict) -> None:
        """Conteo por canal que se muestra junto al nombre del tubo ({} = no mostrar)."""
        self._conteos = dict(conteos)
        self.update()

    def set_active(self, channel_id: str | None) -> None:
        self._active_id = channel_id
        self.update()

    def set_editing(self, channel_id: str | None) -> None:
        """Pone un tubo en modo edición (manillas visibles); None = todos fijos."""
        if channel_id == self._editing_id:
            return
        self._editing_id = channel_id
        self._drag = None
        self.editing_changed.emit(channel_id or "")
        self.update()

    def start_drawing(self) -> None:
        if self._image is None:
            self.message.emit("Primero abre un video.")
            return
        self._rect_start = None
        self._set_drawing(True)
        self.setFocus()
        self.message.emit("Arrastra con el mouse sobre el video para dibujar el tubo. Esc cancela.")

    def cancel_drawing(self) -> None:
        self._rect_start = None
        self._set_drawing(False)
        self.update()

    # ---------- geometría ----------
    def _set_drawing(self, value: bool) -> None:
        self._drawing = value
        self.setCursor(Qt.CrossCursor if value else Qt.ArrowCursor)
        self.drawing_changed.emit(value)

    def _target_rect(self) -> QRectF:
        if self._image is None:
            return QRectF()
        iw, ih = self._image.width(), self._image.height()
        s = min(self.width() / iw, self.height() / ih)
        w, h = iw * s, ih * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _to_widget(self, pt: tuple[float, float]) -> QPointF:
        r = self._target_rect()
        s = r.width() / self._image.width()
        return QPointF(r.x() + pt[0] * s, r.y() + pt[1] * s)

    def _to_video(self, pos: QPointF, clamp: bool = False) -> tuple[float, float] | None:
        r = self._target_rect()
        if not clamp and not r.contains(pos):
            return None
        s = r.width() / self._image.width()
        x = (pos.x() - r.x()) / s
        y = (pos.y() - r.y()) / s
        if clamp:
            x = max(0.0, min(float(self._image.width()), x))
            y = max(0.0, min(float(self._image.height()), y))
        return (x, y)

    def _active(self) -> Canal | None:
        return next((c for c in self._channels if c.id == self._active_id), None)

    def _box(self, ch: Canal) -> QRectF:
        x1, y1, x2, y2 = ch.caja
        return QRectF(self._to_widget((x1, y1)), self._to_widget((x2, y2)))

    def _line_y(self, ch: Canal, frac: float) -> float:
        return self._to_widget((ch.caja[0], ch.y_linea(frac))).y()

    def _handles(self, ch: Canal) -> list[tuple[tuple[int, int], QPointF]]:
        x0, y0, x1, y1 = ch.caja
        out = []
        for hx, hy in HANDLES:
            x = x0 if hx < 0 else x1 if hx > 0 else (x0 + x1) / 2
            y = y0 if hy < 0 else y1 if hy > 0 else (y0 + y1) / 2
            out.append(((hx, hy), self._to_widget((x, y))))
        return out

    def _hit_handle(self, ch: Canal, pos: QPointF):
        for key, wp in self._handles(ch):
            if abs(pos.x() - wp.x()) <= HANDLE_PX and abs(pos.y() - wp.y()) <= HANDLE_PX:
                return key
        return None

    def _hit_line(self, ch: Canal, pos: QPointF) -> str | None:
        if not lineas.EDITABLES:  # líneas fijas: no se pueden agarrar
            return None
        box = self._box(ch)
        if not (box.left() <= pos.x() <= box.right()):
            return None
        best = None
        for name, frac in (("A", ch.linea_a), ("B", ch.linea_b)):
            d = abs(pos.y() - self._line_y(ch, frac))
            if d <= LINE_HIT_PX and (best is None or d < best[0]):
                best = (d, name)
        return best[1] if best else None

    def _inside(self, ch: Canal, pos: QPointF) -> bool:
        return self._box(ch).contains(pos)

    # ---------- dibujo ----------
    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#1e1e1e"))
        if self._image is None:
            p.setPen(QColor("#aaaaaa"))
            p.drawText(self.rect(), Qt.AlignCenter, "Abre un video para comenzar")
            return
        p.drawImage(self._target_rect(), self._image)

        for c in self._channels:
            col = color_for(c.id)
            on = c.activo
            active = c.id == self._active_id
            box = self._box(c)
            fill = QColor(col)
            fill.setAlpha(60 if on else 15)
            pen = QPen(col, 4 if active else (3 if on else 1.5))
            if not on:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QBrush(fill))
            p.drawRect(box)

            # zona de conteo: banda entre A y B
            ya, yb = self._line_y(c, c.linea_a), self._line_y(c, c.linea_b)
            band = QColor("#ffffff")
            band.setAlpha(45 if on else 15)
            p.setPen(Qt.NoPen)
            p.setBrush(band)
            p.drawRect(QRectF(box.left(), ya, box.width(), yb - ya))
            line_pen = QPen(QColor("#ffffff"), 2)
            if not on:
                line_pen.setStyle(Qt.DashLine)
            p.setPen(line_pen)
            p.drawLine(QPointF(box.left(), ya), QPointF(box.right(), ya))
            p.drawLine(QPointF(box.left(), yb), QPointF(box.right(), yb))
            p.drawText(QPointF(box.left() + 5, ya - 4), "A")
            p.drawText(QPointF(box.left() + 5, yb + 13), "B")

            texto = c.nombre or c.id
            fuente = p.font()
            if on and c.id in self._conteos:
                texto += f": {self._conteos[c.id]}"
                fuente.setBold(True)
                fuente.setPointSize(12)
            p.setFont(fuente)
            p.setPen(col)
            p.drawText(box.topLeft() + QPointF(6, -6), texto)
            fuente.setBold(False)
            fuente.setPointSize(9)
            p.setFont(fuente)

        if self._overlay is not None:
            dets, tray = self._overlay
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 110), 1))
            for d in dets:
                p.drawRect(QRectF(self._to_widget((d["x1"], d["y1"])), self._to_widget((d["x2"], d["y2"]))))
            for t in tray:
                caja = QRectF(self._to_widget((t["x1"], t["y1"])), self._to_widget((t["x2"], t["y2"])))
                p.setPen(QPen(color_for(t["canal"]), 2))
                p.drawRect(caja)
                p.setPen(QColor("#ffff66"))
                p.drawText(caja.topLeft() + QPointF(2, -3), f"#{t['id']}")

        ch = self._active()
        if ch is not None and ch.id == self._editing_id and not self._drawing:
            p.setPen(QPen(QColor("#202020"), 1.5))
            p.setBrush(QColor("#ffffff"))
            for _k, wp in self._handles(ch):
                p.drawRect(QRectF(wp.x() - 5, wp.y() - 5, 10, 10))
            box = self._box(ch)
            cx = box.center().x()
            if lineas.EDITABLES:
                p.setBrush(QColor("#ffd400"))
                for frac in (ch.linea_a, ch.linea_b):
                    p.drawEllipse(QPointF(cx, self._line_y(ch, frac)), 6, 6)

        if self._drawing and self._rect_start is not None and self._cursor is not None:
            a = self._to_widget(self._rect_start)
            p.setPen(QPen(QColor("#ffff00"), 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(a, self._cursor).normalized())

    # ---------- mouse ----------
    def mousePressEvent(self, e) -> None:
        if self._image is None or e.button() != Qt.LeftButton:
            return
        pos = e.position()

        if self._drawing:
            pt = self._to_video(pos)
            if pt is not None:
                self._rect_start = pt
                self._cursor = pos
            return

        ch = self._active()
        if ch is not None and ch.id == self._editing_id:
            key = self._hit_handle(ch, pos)
            if key is not None:
                self._drag = {"type": "handle", "key": key, "orig": ch.caja, "ch": ch}
                return
            line = self._hit_line(ch, pos)
            if line is not None:
                self._drag = {"type": "line", "key": line, "orig": ch.caja, "ch": ch}
                return
            if self._inside(ch, pos):
                self._drag = {"type": "move", "start": self._to_video(pos, True), "orig": ch.caja, "ch": ch}
                return
        for c in reversed(self._channels):
            if self._inside(c, pos):
                self.channel_clicked.emit(c.id)  # selecciona (y fija el que se editaba)
                self.set_editing(c.id)  # un clic sobre un tubo abre su configuración
                return
        if self._editing_id is not None:  # clic en zona vacía: se fija el tubo
            self.set_editing(None)

    def mouseMoveEvent(self, e) -> None:
        pos = e.position()
        self._cursor = pos
        if self._image is None:
            return
        if self._drawing:
            if self._rect_start is not None:
                self.update()
            return
        if self._drag is not None:
            self._apply_drag(self._to_video(pos, True))
            self.channel_moving.emit(self._drag["ch"].id)
            self.update()
            return
        ch = self._active()
        cursor = Qt.ArrowCursor
        if ch is not None and ch.id == self._editing_id:
            key = self._hit_handle(ch, pos)
            if key is not None:
                cursor = CURSORS[key]
            elif self._hit_line(ch, pos) is not None:
                cursor = Qt.SizeVerCursor
            elif self._inside(ch, pos):
                cursor = Qt.SizeAllCursor
        self.setCursor(cursor)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        if self._drawing and self._rect_start is not None:
            x1, y1 = self._to_video(e.position(), True)
            x0, y0 = self._rect_start
            self._rect_start = None
            if abs(x1 - x0) < MIN_SIZE or abs(y1 - y0) < MIN_SIZE:
                self.message.emit("Rectángulo muy pequeño: arrastra más para dibujarlo.")
                self.update()
                return
            self._set_drawing(False)
            self.channel_drawn.emit((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
            self.update()
            return
        if self._drag is not None:
            ch = self._drag["ch"]
            self._drag = None
            self.channel_edited.emit(ch.id)

    def _apply_drag(self, cur: tuple[float, float]) -> None:
        d = self._drag
        ch: Canal = d["ch"]
        x0, y0, x1, y1 = d["orig"]
        iw, ih = self._image.width(), self._image.height()

        if d["type"] == "move":
            dx, dy = cur[0] - d["start"][0], cur[1] - d["start"][1]
            dx = max(-x0, min(iw - x1, dx))
            dy = max(-y0, min(ih - y1, dy))
            ch.caja = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        elif d["type"] == "handle":
            hx, hy = d["key"]
            if hx < 0:
                x0 = cur[0]
            elif hx > 0:
                x1 = cur[0]
            if hy < 0:
                y0 = cur[1]
            elif hy > 0:
                y1 = cur[1]
            nx0, nx1 = sorted((x0, x1))
            ny0, ny1 = sorted((y0, y1))
            if nx1 - nx0 >= MIN_SIZE and ny1 - ny0 >= MIN_SIZE:
                ch.caja = (nx0, ny0, nx1, ny1)
        else:  # línea A o B
            frac = (cur[1] - y0) / (y1 - y0)
            if d["key"] == "A":
                ch.linea_a = max(0.0, min(ch.linea_b - MIN_GAP, frac))
            else:
                ch.linea_b = min(1.0, max(ch.linea_a + MIN_GAP, frac))

    def keyPressEvent(self, e) -> None:
        if self._drawing and e.key() == Qt.Key_Escape:
            self.cancel_drawing()
            self.message.emit("Dibujo cancelado.")
        else:
            super().keyPressEvent(e)
