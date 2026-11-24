"""Barra de reproducción con una marca en cada cuadro donde se contó un pez.

Las marcas son puntos del color del tubo bajo la barra. Un clic sobre una marca salta a ese cuadro y al pasar el
mouse se ve qué pez se contó ahí. Sin marcas se comporta como un QSlider normal.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider, QToolTip

RADIO = 3.0       # px: tamaño del punto
TOLERANCIA = 6.0  # px: distancia máxima para que un clic o el mouse «toque» una marca


class BarraConMarcas(QSlider):
    def __init__(self) -> None:
        super().__init__(Qt.Horizontal)
        self.setMouseTracking(True)
        self._marcas: list[tuple[int, QColor, str]] = []  # (cuadro, color, texto)

    def set_marcas(self, marcas: list[tuple[int, QColor, str]]) -> None:
        self._marcas = sorted(marcas, key=lambda m: m[0])
        self.setToolTip(f"{len(marcas)} peces contados: haz clic en un punto para ir a ese cuadro" if marcas else "")
        self.update()

    def limpiar_marcas(self) -> None:
        self.set_marcas([])

    # ---- geometría ----
    def _x(self, cuadro: int) -> float:
        """Centro horizontal (px) del asa cuando la barra vale `cuadro`."""
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        surco = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        asa = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        libre = surco.width() - asa.width()
        pos = QStyle.sliderPositionFromValue(self.minimum(), self.maximum(), cuadro, libre)
        return surco.x() + pos + asa.width() / 2

    def _cercanas(self, x: float) -> list[tuple[int, QColor, str]]:
        return [m for m in self._marcas if abs(self._x(m[0]) - x) <= TOLERANCIA]

    # ---- dibujo y ratón ----
    def paintEvent(self, ev) -> None:
        super().paintEvent(ev)
        if not self._marcas or self.maximum() <= self.minimum():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        y = self.height() / 2 + 12
        for cuadro, color, _ in self._marcas:
            p.setBrush(color)
            p.drawEllipse(QPointF(self._x(cuadro), y), RADIO, RADIO)
        p.end()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton and self.isEnabled():
            cerca = self._cercanas(ev.position().x())
            if cerca:
                x = ev.position().x()
                self.setValue(min(cerca, key=lambda m: abs(self._x(m[0]) - x))[0])
                ev.accept()
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:
        cerca = self._cercanas(ev.position().x()) if not ev.buttons() else []
        if cerca:
            QToolTip.showText(ev.globalPosition().toPoint(), "\n".join(t for _, _, t in cerca), self)
        super().mouseMoveEvent(ev)
