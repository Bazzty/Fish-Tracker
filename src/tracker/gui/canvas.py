"""Widget que muestra un cuadro del video y permite dibujar y editar tubos.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .channels import Channel

PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6", "#bfef45"]
CLOSE_RADIUS_PX = 12
HANDLE_PX = 7  # radio de las manillas (px de pantalla)
MIN_SIZE = 5.0  # tamaño mínimo de un rectángulo (px del video)

# (hx, hy): -1 = borde izq./sup., 1 = borde der./inf., 0 = centro
HANDLES = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]
CURSORS = {
    (-1, -1): Qt.SizeFDiagCursor, (1, 1): Qt.SizeFDiagCursor,
    (1, -1): Qt.SizeBDiagCursor, (-1, 1): Qt.SizeBDiagCursor,
    (0, -1): Qt.SizeVerCursor, (0, 1): Qt.SizeVerCursor,
    (-1, 0): Qt.SizeHorCursor, (1, 0): Qt.SizeHorCursor,
}


def color_for(channel_id: int) -> QColor:
    return QColor(PALETTE[(channel_id - 1) % len(PALETTE)])


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _rect_points(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class VideoCanvas(QWidget):
    channel_drawn = Signal(list, str)  # puntos (px del video), tipo: "rect" | "polygon"
    channel_clicked = Signal(int)  # clic sobre un tubo existente
    channel_edited = Signal(int)  # se movió o redimensionó un tubo
    editing_changed = Signal(int)  # id del tubo en edición, o -1 si todos están fijos
    drawing_changed = Signal(bool)
    message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._image: QImage | None = None
        self._channels: list[Channel] = []
        self._active_id: int | None = None
        self._editing_id: int | None = None  # solo este tubo se puede mover/redimensionar
        self._mode: str | None = None  # None | "rect" | "polygon"
        self._points: list[tuple[float, float]] = []  # polígono en curso
        self._rect_start: tuple[float, float] | None = None
        self._cursor: QPointF | None = None
        self._drag: dict | None = None
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    # ---------- API pública ----------
    def set_frame(self, image: QImage) -> None:
        self._image = image
        self.update()

    def set_channels(self, channels: list[Channel]) -> None:
        self._channels = channels
        self.update()

    @property
    def mode(self) -> str | None:
        return self._mode

    @property
    def editing_id(self) -> int | None:
        return self._editing_id

    def set_editing(self, channel_id: int | None) -> None:
        """Pone un tubo en modo edición (manillas visibles); None = todos fijos."""
        if channel_id == self._editing_id:
            return
        self._editing_id = channel_id
        self._drag = None
        self.editing_changed.emit(-1 if channel_id is None else channel_id)
        self.update()

    def set_active(self, channel_id: int | None) -> None:
        self._active_id = channel_id
        self.update()

    def start_drawing(self, kind: str = "rect") -> None:
        if self._image is None:
            self.message.emit("Primero abre un video.")
            return
        self._points = []
        self._rect_start = None
        self._set_mode(kind)
        self.setFocus()
        if kind == "rect":
            self.message.emit("Arrastra con el mouse sobre el video para dibujar el tubo. Esc cancela.")
        else:
            self.message.emit(
                "Clic para añadir puntos, clic derecho deshace, Enter o clic en el primer punto cierra, Esc cancela."
            )

    def cancel_drawing(self) -> None:
        self._points = []
        self._rect_start = None
        self._set_mode(None)
        self.update()

    def finish_polygon(self) -> None:
        if len(self._points) < 3:
            self.message.emit("Un tubo necesita al menos 3 puntos.")
            return
        pts = list(self._points)
        self._points = []
        self._set_mode(None)
        self.channel_drawn.emit(pts, "polygon")
        self.update()

    # ---------- geometría ----------
    def _set_mode(self, mode: str | None) -> None:
        self._mode = mode
        self.setCursor(Qt.CrossCursor if mode else Qt.ArrowCursor)
        self.drawing_changed.emit(mode is not None)

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

    def _active(self) -> Channel | None:
        for c in self._channels:
            if c.id == self._active_id:
                return c
        return None

    def _handles(self, ch: Channel) -> list[tuple[object, QPointF]]:
        if ch.kind == "rect":
            x0, y0, x1, y1 = _bbox(ch.points)
            out = []
            for hx, hy in HANDLES:
                x = x0 if hx < 0 else x1 if hx > 0 else (x0 + x1) / 2
                y = y0 if hy < 0 else y1 if hy > 0 else (y0 + y1) / 2
                out.append(((hx, hy), self._to_widget((x, y))))
            return out
        return [(i, self._to_widget(p)) for i, p in enumerate(ch.points)]

    def _hit_handle(self, ch: Channel, pos: QPointF):
        for key, wp in self._handles(ch):
            if abs(pos.x() - wp.x()) <= HANDLE_PX and abs(pos.y() - wp.y()) <= HANDLE_PX:
                return key
        return None

    def _inside(self, ch: Channel, pos: QPointF) -> bool:
        poly = QPolygonF([self._to_widget(p) for p in ch.points])
        return poly.containsPoint(pos, Qt.OddEvenFill)

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
            active = c.id == self._active_id
            poly = QPolygonF([self._to_widget(pt) for pt in c.points])
            fill = QColor(col)
            fill.setAlpha(70 if c.selected else 20)
            pen = QPen(col, 4 if active else (3 if c.selected else 1.5))
            if not c.selected:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QBrush(fill))
            p.drawPolygon(poly)
            p.setPen(col)
            p.drawText(poly.first() + QPointF(6, -6), c.name)

        ch = self._active()
        if ch is not None and ch.id == self._editing_id and self._mode is None:
            p.setPen(QPen(QColor("#202020"), 1.5))
            p.setBrush(QColor("#ffffff"))
            for _, wp in self._handles(ch):
                p.drawRect(QRectF(wp.x() - 5, wp.y() - 5, 10, 10))

        # vista previa del rectángulo en curso
        if self._mode == "rect" and self._rect_start is not None and self._cursor is not None:
            a = self._to_widget(self._rect_start)
            p.setPen(QPen(QColor("#ffff00"), 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(a, self._cursor).normalized())

        # polígono en curso
        if self._points:
            wpts = [self._to_widget(pt) for pt in self._points]
            p.setPen(QPen(QColor("#ffff00"), 2))
            p.setBrush(Qt.NoBrush)
            for a, b in zip(wpts, wpts[1:]):
                p.drawLine(a, b)
            if self._cursor is not None:
                p.setPen(QPen(QColor("#ffff00"), 1, Qt.DashLine))
                p.drawLine(wpts[-1], self._cursor)
            p.setBrush(QColor("#ffff00"))
            for w in wpts:
                p.drawEllipse(w, 4, 4)

    # ---------- mouse ----------
    def mousePressEvent(self, e) -> None:
        if self._image is None:
            return
        pos = e.position()

        if self._mode == "rect":
            if e.button() == Qt.LeftButton:
                pt = self._to_video(pos)
                if pt is not None:
                    self._rect_start = pt
                    self._cursor = pos
            return

        if self._mode == "polygon":
            if e.button() == Qt.RightButton:
                if self._points:
                    self._points.pop()
                    self.update()
            elif e.button() == Qt.LeftButton:
                if len(self._points) >= 3:
                    first = self._to_widget(self._points[0])
                    if (pos - first).manhattanLength() <= CLOSE_RADIUS_PX:
                        self.finish_polygon()
                        return
                pt = self._to_video(pos)
                if pt is not None:
                    self._points.append(pt)
                    self.update()
            return

        # modo edición
        if e.button() != Qt.LeftButton:
            return
        ch = self._active()
        if ch is not None and ch.id == self._editing_id:
            key = self._hit_handle(ch, pos)
            if key is not None:
                self._drag = {"type": "handle", "key": key, "orig": list(ch.points), "ch": ch}
                return
            if self._inside(ch, pos):
                self._drag = {"type": "move", "start": self._to_video(pos, True), "orig": list(ch.points), "ch": ch}
                return
        for c in reversed(self._channels):
            if self._inside(c, pos):
                self.channel_clicked.emit(c.id)  # selecciona (y fija el que se editaba)
                return
        # clic en zona vacía: se fija el tubo que se estaba editando
        if self._editing_id is not None:
            self.set_editing(None)

    def mouseDoubleClickEvent(self, e) -> None:
        """Doble clic sobre un tubo fijo: vuelve a ponerlo en edición."""
        if self._image is None or self._mode is not None or e.button() != Qt.LeftButton:
            return
        for c in reversed(self._channels):
            if self._inside(c, e.position()):
                self.channel_clicked.emit(c.id)
                self.set_editing(c.id)
                return

    def mouseMoveEvent(self, e) -> None:
        pos = e.position()
        self._cursor = pos
        if self._image is None:
            return

        if self._mode is not None:
            if self._mode == "rect" and self._rect_start is None:
                return
            self.update()
            return

        if self._drag is not None:
            self._apply_drag(self._to_video(pos, True))
            self.update()
            return

        # cursor según lo que haya bajo el mouse
        ch = self._active()
        cursor = Qt.ArrowCursor
        if ch is not None and ch.id == self._editing_id:
            key = self._hit_handle(ch, pos)
            if key is not None:
                cursor = CURSORS.get(key, Qt.PointingHandCursor) if ch.kind == "rect" else Qt.PointingHandCursor
            elif self._inside(ch, pos):
                cursor = Qt.SizeAllCursor
        self.setCursor(cursor)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        if self._mode == "rect" and self._rect_start is not None:
            end = self._to_video(e.position(), True)
            x0, y0 = self._rect_start
            x1, y1 = end
            self._rect_start = None
            if abs(x1 - x0) < MIN_SIZE or abs(y1 - y0) < MIN_SIZE:
                self.message.emit("Rectángulo muy pequeño: arrastra más para dibujarlo.")
                self.update()
                return
            pts = _rect_points(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            self._set_mode(None)
            self.channel_drawn.emit(pts, "rect")
            self.update()
            return
        if self._drag is not None:
            ch = self._drag["ch"]
            self._drag = None
            self.channel_edited.emit(ch.id)

    def _apply_drag(self, cur: tuple[float, float]) -> None:
        d = self._drag
        ch: Channel = d["ch"]
        orig = d["orig"]
        iw, ih = self._image.width(), self._image.height()

        if d["type"] == "move":
            dx, dy = cur[0] - d["start"][0], cur[1] - d["start"][1]
            x0, y0, x1, y1 = _bbox(orig)
            dx = max(-x0, min(iw - x1, dx))
            dy = max(-y0, min(ih - y1, dy))
            ch.points = [(x + dx, y + dy) for x, y in orig]
            return

        key = d["key"]
        if ch.kind == "rect":
            x0, y0, x1, y1 = _bbox(orig)
            hx, hy = key
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
                ch.points = _rect_points(nx0, ny0, nx1, ny1)
        else:
            pts = list(orig)
            pts[key] = cur
            ch.points = pts

    def keyPressEvent(self, e) -> None:
        if self._mode is None:
            return super().keyPressEvent(e)
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self._mode == "polygon":
            self.finish_polygon()
        elif e.key() == Qt.Key_Escape:
            self.cancel_drawing()
            self.message.emit("Dibujo cancelado.")
