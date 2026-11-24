"""Widget que muestra un cuadro del video y permite dibujar y editar tubos (canales).

Cada canal es un cuadrilátero de forma libre (canal_libre.CanalLibre, que hereda de tracker.canales.Canal)
con dos líneas de conteo, A (entrada) y B (salida), dadas como fracción del alto de su caja envolvente
medida desde arriba. Los peces avanzan de arriba hacia abajo.

- Dibujar: arrastrar el mouse sobre el video (nace como rectángulo).
- Un tubo en edición muestra sus 4 esquinas (cada una se mueve sola y deforma el tubo; con Mayús se
  conserva la forma y solo cambia el tamaño), grips en las líneas A y B, y se mueve arrastrándolo por
  dentro. Un tubo fijo no se modifica.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from tracker.canales import Canal

from . import lineas, tema
from .canal_libre import CanalLibre, cuerda, es_simple, punto_en_poligono, recortar_franja

PALETTE = ["#ef4444", "#22c55e", "#3b82f6", "#f59e0b", "#a855f7", "#06b6d4", "#ec4899", "#84cc16"]
HANDLE_PX = 7  # radio de las manillas (px de pantalla)
LINE_HIT_PX = 6  # tolerancia para agarrar una línea A/B
MIN_SIZE = 5.0  # tamaño mínimo de un tubo (px del video)
MIN_GAP = 0.02  # separación mínima entre A y B (fracción del alto)

# Esquinas del tubo, en el orden de CanalLibre.puntos: arriba-izq, arriba-der, abajo-der, abajo-izq.
# (hx, hy): -1 = borde izq./sup., 1 = borde der./inf. (para redimensionar con Mayús)
ESQUINAS = [(-1, -1), (1, -1), (1, 1), (-1, 1)]


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
    open_requested = Signal()  # clic en la zona vacía (aún sin video)

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
        self._rutas: dict[tuple[str, int], list[tuple[float, float]]] = {}  # (canal, id) -> centros recorridos
        self._contados: set[tuple[str, int]] = set()  # peces ya contados: su línea se dibuja más gruesa
        self._conteos: dict[str, int] = {}
        self.setMinimumSize(640, 360)
        self.setCursor(Qt.PointingHandCursor)
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
        if self._image is None and not self._drawing:
            self.setCursor(Qt.ArrowCursor)  # ya hay video: deja de ser «clic para abrir»
        self._image = image
        self.update()

    def set_channels(self, channels: list[Canal]) -> None:
        for i, c in enumerate(channels):  # la lista es la misma de la ventana: se convierte en su sitio
            if not isinstance(c, CanalLibre):
                channels[i] = CanalLibre.desde_canal(c)
        self._channels = channels
        self.update()

    def set_overlay(self, detecciones: list, trayectorias: list, eventos: list = ()) -> None:
        """Cajas del cuadro que se está procesando (px del video). Va sumando el recorrido de cada pez."""
        for t in trayectorias:
            self._rutas.setdefault((t["canal"], int(t["id"])), []).append((t["cx"], t["cy"]))
        self._contados.update((e["canal"], int(e["id"])) for e in eventos)
        self._overlay = (detecciones, trayectorias)
        self.update()

    def limpiar_rutas(self) -> None:
        """Olvida los recorridos (al empezar a procesar otra vez o al abrir otro video)."""
        self._rutas, self._contados = {}, set()

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

    def _box(self, ch: CanalLibre) -> QRectF:
        x1, y1, x2, y2 = ch.caja
        return QRectF(self._to_widget((x1, y1)), self._to_widget((x2, y2)))

    def _pts_w(self, ch: CanalLibre) -> list[QPointF]:
        return [self._to_widget(p) for p in ch.puntos]

    def _line_y(self, ch: CanalLibre, frac: float) -> float:
        return self._to_widget((ch.caja[0], ch.y_linea(frac))).y()

    def _span(self, ch: CanalLibre, frac: float) -> tuple[float, float]:
        """Extremos x (px de pantalla) de la línea A/B dentro del tubo (en un tubo torcido cambian con la altura)."""
        y = ch.y_linea(frac)
        c = cuerda(ch.puntos, y) or (ch.caja[0], ch.caja[2])
        return self._to_widget((c[0], y)).x(), self._to_widget((c[1], y)).x()

    def _hit_handle(self, ch: CanalLibre, pos: QPointF) -> int | None:
        for i, wp in enumerate(self._pts_w(ch)):
            if abs(pos.x() - wp.x()) <= HANDLE_PX and abs(pos.y() - wp.y()) <= HANDLE_PX:
                return i
        return None

    def _hit_line(self, ch: CanalLibre, pos: QPointF) -> str | None:
        if not lineas.EDITABLES:  # líneas fijas: no se pueden agarrar
            return None
        best = None
        for name, frac in (("A", ch.linea_a), ("B", ch.linea_b)):
            xl, xr = self._span(ch, frac)
            if not (xl - 2 <= pos.x() <= xr + 2):
                continue
            d = abs(pos.y() - self._line_y(ch, frac))
            if d <= LINE_HIT_PX and (best is None or d < best[0]):
                best = (d, name)
        return best[1] if best else None

    def _inside(self, ch: CanalLibre, pos: QPointF) -> bool:
        pt = self._to_video(pos)
        return pt is not None and punto_en_poligono(pt[0], pt[1], ch.puntos)

    # ---------- dibujo ----------
    def _pill_size(self, texto: str, pt: int = 9, negrita: bool = True) -> tuple[float, float]:
        f = QFont(self.font())
        f.setPointSize(pt)
        f.setBold(negrita)
        fm = QFontMetricsF(f)
        return fm.horizontalAdvance(texto) + 14, fm.height() + 4

    def _pill(self, p: QPainter, texto: str, ancla: QPointF, fondo: QColor, fg: str = "#ffffff",
              pt: int = 9, negrita: bool = True) -> None:
        """Etiqueta redondeada cuya esquina inferior izquierda queda en `ancla`."""
        f = QFont(self.font())
        f.setPointSize(pt)
        f.setBold(negrita)
        w, h = self._pill_size(texto, pt, negrita)
        r = QRectF(ancla.x(), ancla.y() - h, w, h)
        p.setPen(Qt.NoPen)
        p.setBrush(fondo)
        p.drawRoundedRect(r, h / 2, h / 2)
        p.setFont(f)
        p.setPen(QColor(fg))
        p.drawText(r, Qt.AlignCenter, texto)

    def _etiquetas_tubos(self, p: QPainter) -> None:
        """Nombre (y conteo) de cada tubo, arriba a la izquierda DENTRO del tubo.

        Se dibujan después de todos los tubos para que ninguno las tape, quedan siempre dentro del video (no se
        cortan por el borde) y, si dos chocan, la siguiente baja hasta quedar libre.
        """
        area = self._target_rect().intersected(QRectF(self.rect())).adjusted(2, 2, -2, -2)
        ocupadas: list[QRectF] = []
        for c in self._channels:
            on = c.activo
            texto = c.nombre or c.id
            con_conteo = on and c.id in self._conteos
            if con_conteo:
                texto += f"  ·  {self._conteos[c.id]}"
            pt = 12 if con_conteo else 10
            w, h = self._pill_size(texto, pt)
            esq = self._to_widget(c.puntos[0])  # esquina arriba-izq. del tubo (también si está torcido)
            x = max(area.left(), min(esq.x() + 4, area.right() - w))
            y = max(area.top(), min(esq.y() + 4, area.bottom() - h))
            r = QRectF(x, y, w, h)
            for _ in range(len(ocupadas) + 1):  # baja bajo la que choca; con n etiquetas basta con n intentos
                choque = next((o for o in ocupadas if o.intersects(r)), None)
                if choque is None:
                    break
                r.moveTop(choque.bottom() + 3)
            if r.bottom() > area.bottom():  # sin espacio abajo: se queda pegada al borde inferior
                r.moveBottom(area.bottom())
            ocupadas.append(r)
            fondo = QColor(color_for(c.id)) if on else QColor(134, 134, 139, 230)
            self._pill(p, texto, r.bottomLeft(), fondo, pt=pt)

    def _vacio(self, p: QPainter) -> None:
        r = QRectF(self.rect()).adjusted(24, 24, -24, -24)
        pen = QPen(QColor(tema.ACERO), 1.5, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(r, 28, 28)
        c = r.center()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(tema.PRIMARIO))
        p.drawEllipse(c + QPointF(0, -44), 34, 34)
        p.setBrush(QColor("#ffffff"))
        p.drawPolygon(QPolygonF([c + QPointF(-9, -62), c + QPointF(-9, -26), c + QPointF(19, -44)]))  # ▶
        f = QFont(self.font())
        f.setPointSize(15)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(tema.FONDO))
        p.drawText(QRectF(r.x(), c.y() + 2, r.width(), 34), Qt.AlignCenter, "Abre un video para comenzar")
        f.setPointSize(10)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(tema.ACERO))
        p.drawText(QRectF(r.x(), c.y() + 38, r.width(), 26), Qt.AlignCenter,
                   "Haz clic aquí, usa «Abrir video» o arrastra un archivo a la ventana")

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        borde = QPainterPath()
        borde.addRoundedRect(QRectF(self.rect()), 14, 14)
        p.setClipPath(borde)
        p.fillRect(self.rect(), QColor(tema.VIDEO_FONDO))
        if self._image is None:
            self._vacio(p)
            return
        p.drawImage(self._target_rect(), self._image)
        base = QFont(self.font())

        for c in self._channels:
            col = color_for(c.id)
            on = c.activo
            active = c.id == self._active_id
            pts_w = self._pts_w(c)
            fill = QColor(col)
            fill.setAlpha(55 if on else 14)
            pen = QPen(col, 3.5 if active else (2.5 if on else 1.5))
            pen.setJoinStyle(Qt.RoundJoin)
            if not on:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QBrush(fill))
            p.drawPolygon(QPolygonF(pts_w))

            # zona de conteo: banda entre A y B (recortada a la forma del tubo)
            franja = recortar_franja(c.puntos, c.y_linea(c.linea_a), c.y_linea(c.linea_b))
            if len(franja) >= 3:
                band = QColor("#ffffff")
                band.setAlpha(60 if on else 18)
                p.setPen(Qt.NoPen)
                p.setBrush(band)
                p.drawPolygon(QPolygonF([self._to_widget(q) for q in franja]))
            line_pen = QPen(QColor("#ffffff"), 2)
            if not on:
                line_pen.setStyle(Qt.DashLine)
            p.setPen(line_pen)
            ya, yb = self._line_y(c, c.linea_a), self._line_y(c, c.linea_b)
            (xa1, xa2), (xb1, xb2) = self._span(c, c.linea_a), self._span(c, c.linea_b)
            p.drawLine(QPointF(xa1, ya), QPointF(xa2, ya))
            p.drawLine(QPointF(xb1, yb), QPointF(xb2, yb))
            oscuro = QColor(29, 29, 31, 215)
            ta, tb = ("A · entrada", "B · salida") if active else ("A", "B")
            self._pill(p, ta, QPointF(xa1 + 4, ya - 3), oscuro, pt=8)
            self._pill(p, tb, QPointF(xb1 + 4, yb + 19), oscuro, pt=8)

        self._etiquetas_tubos(p)
        p.setFont(base)
        if self._overlay is not None:
            dets, tray = self._overlay
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 110), 1))
            for d in dets:
                p.drawRect(QRectF(self._to_widget((d["x1"], d["y1"])), self._to_widget((d["x2"], d["y2"]))))
            for t in tray:  # línea del seguimiento: el recorrido del pez, del color de su tubo (más gruesa si ya se contó)
                clave = (t["canal"], int(t["id"]))
                ruta = self._rutas.get(clave, ())
                if len(ruta) > 1:
                    pen = QPen(color_for(t["canal"]), 2.5 if clave in self._contados else 1.25)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    p.setPen(pen)
                    p.setBrush(Qt.NoBrush)
                    p.drawPolyline(QPolygonF([self._to_widget(q) for q in ruta]))
            for t in tray:
                caja = QRectF(self._to_widget((t["x1"], t["y1"])), self._to_widget((t["x2"], t["y2"])))
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(color_for(t["canal"]), 2))
                p.drawRect(caja)
                self._pill(p, f"#{t['id']}", caja.topLeft() + QPointF(0, -2), QColor("#fde047"), fg=tema.TEXTO, pt=8)

        ch = self._active()
        if ch is not None and ch.id == self._editing_id and not self._drawing:
            col = color_for(ch.id)
            p.setPen(QPen(col, 2))
            p.setBrush(QColor("#ffffff"))
            for wp in self._pts_w(ch):
                p.drawRoundedRect(QRectF(wp.x() - 6, wp.y() - 6, 12, 12), 3, 3)
            if lineas.EDITABLES:
                p.setPen(QPen(QColor("#ffffff"), 2))
                p.setBrush(QColor("#fbbf24"))
                for frac in (ch.linea_a, ch.linea_b):
                    xl, xr = self._span(ch, frac)
                    p.drawEllipse(QPointF((xl + xr) / 2, self._line_y(ch, frac)), 7, 7)

        if self._drawing and self._rect_start is not None and self._cursor is not None:
            a = self._to_widget(self._rect_start)
            p.setPen(QPen(QColor("#fde047"), 2, Qt.DashLine))
            p.setBrush(QColor(253, 224, 71, 40))
            p.drawRect(QRectF(a, self._cursor).normalized())

    # ---------- mouse ----------
    def mousePressEvent(self, e) -> None:
        if self._image is None:
            if e.button() == Qt.LeftButton:
                self.open_requested.emit()
            return
        if e.button() != Qt.LeftButton:
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
                self._drag = {"type": "corner", "key": key, "orig": ch.caja, "orig_pts": ch.puntos, "ch": ch}
                return
            line = self._hit_line(ch, pos)
            if line is not None:
                self._drag = {"type": "line", "key": line, "orig": ch.caja, "orig_pts": ch.puntos, "ch": ch}
                return
            if self._inside(ch, pos):
                self._drag = {"type": "move", "start": self._to_video(pos, True), "orig": ch.caja,
                              "orig_pts": ch.puntos, "ch": ch}
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
            self._apply_drag(self._to_video(pos, True), bool(e.modifiers() & Qt.ShiftModifier))
            self.channel_moving.emit(self._drag["ch"].id)
            self.update()
            return
        ch = self._active()
        cursor = Qt.ArrowCursor
        if ch is not None and ch.id == self._editing_id:
            key = self._hit_handle(ch, pos)
            if key is not None:
                cursor = Qt.PointingHandCursor
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

    def _apply_drag(self, cur: tuple[float, float], mantener_forma: bool = False) -> None:
        d = self._drag
        ch: CanalLibre = d["ch"]
        x0, y0, x1, y1 = d["orig"]
        orig = d["orig_pts"]
        iw, ih = self._image.width(), self._image.height()

        if d["type"] == "move":
            dx, dy = cur[0] - d["start"][0], cur[1] - d["start"][1]
            dx = max(-x0, min(iw - x1, dx))
            dy = max(-y0, min(ih - y1, dy))
            ch.set_puntos([(x + dx, y + dy) for x, y in orig])
        elif d["type"] == "corner":
            if mantener_forma:  # Mayús: como un rectángulo, la esquina opuesta queda fija y se escala la forma
                hx, hy = ESQUINAS[d["key"]]
                if hx < 0:
                    x0 = cur[0]
                else:
                    x1 = cur[0]
                if hy < 0:
                    y0 = cur[1]
                else:
                    y1 = cur[1]
                nx0, nx1 = sorted((x0, x1))
                ny0, ny1 = sorted((y0, y1))
                ox0, oy0, ox1, oy1 = d["orig"]
                if nx1 - nx0 >= MIN_SIZE and ny1 - ny0 >= MIN_SIZE:
                    sx, sy = (nx1 - nx0) / (ox1 - ox0), (ny1 - ny0) / (oy1 - oy0)
                    ch.set_puntos([(nx0 + (x - ox0) * sx, ny0 + (y - oy0) * sy) for x, y in orig])
            else:  # solo se mueve esa esquina; no se admite un tubo cruzado («moño») ni demasiado chico
                pts = list(orig)
                pts[d["key"]] = (cur[0], cur[1])
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                if max(xs) - min(xs) >= MIN_SIZE and max(ys) - min(ys) >= MIN_SIZE and es_simple(pts):
                    ch.set_puntos(pts)
        else:  # línea A o B (fracción del alto de la caja envolvente)
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