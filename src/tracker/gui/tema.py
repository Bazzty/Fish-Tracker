from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

# ---- paleta ----
FONDO = "#f4f6f9"
TARJETA = "#ffffff"
BORDE = "#e2e8f0"
TEXTO = "#1e293b"
SUAVE = "#64748b"
PRIMARIO = "#0f766e"        # verde azulado
PRIMARIO_HOVER = "#0b5f58"
PRIMARIO_SUAVE = "#e0f2f1"
ACENTO = "#f2674a"          # coral salmón (acción de procesar)
ACENTO_HOVER = "#dc5236"
OK = "#16a34a"
PELIGRO = "#dc2626"
VIDEO_FONDO = "#0f172a"

QSS = """
QWidget { font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", Arial, sans-serif;
          font-size: 10pt; color: @TEXTO; }
QMainWindow, QDialog, QWidget#raiz { background: @FONDO; }
QToolTip { background: @TEXTO; color: white; border: none; padding: 6px 8px; border-radius: 6px; }

/* ---------- tarjetas y encabezado ---------- */
QFrame#cabecera { background: @TARJETA; border: none; border-bottom: 1px solid @BORDE; }
QLabel#titulo { font-size: 15pt; font-weight: 700; color: @PRIMARIO; }
QLabel#subtitulo { color: @SUAVE; }
QLabel#chip { background: @PRIMARIO_SUAVE; color: @PRIMARIO; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QFrame#tarjeta { background: @TARJETA; border: 1px solid @BORDE; border-radius: 14px; }
QFrame#tarjeta[inactiva="true"] { background: #fafbfc; }
QFrame#interior { background: @FONDO; border: none; border-radius: 10px; }
QFrame#barra { background: @TARJETA; border: 1px solid @BORDE; border-radius: 14px; }
QLabel#paso { font-size: 11.5pt; font-weight: 700; }
QLabel#ayuda { color: @SUAVE; }
QLabel#guia { background: @PRIMARIO_SUAVE; color: @PRIMARIO; border-radius: 12px; padding: 10px 14px;
              font-size: 10.5pt; font-weight: 600; }
QLabel#guia[estado="ok"] { background: #dcfce7; color: #15803d; }
QLabel#guia[estado="trabajando"] { background: #ffe9e3; color: @ACENTO_HOVER; }
QLabel#nota { background: @PRIMARIO_SUAVE; border-radius: 10px; padding: 10px 12px; }
QLabel#resumen { font-weight: 600; color: @SUAVE; }
QLabel#insignia { min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; border-radius: 14px;
                  background: #e2e8f0; color: @SUAVE; font-weight: 700; qproperty-alignment: AlignCenter; }
QLabel#insignia[estado="activo"] { background: @PRIMARIO; color: white; }
QLabel#insignia[estado="hecho"] { background: @OK; color: white; }
QFrame#stat { background: @TARJETA; border: 1px solid @BORDE; border-radius: 12px; }
QLabel#statValor { font-size: 17pt; font-weight: 700; color: @PRIMARIO; }
QLabel#statValor[chico="true"] { font-size: 11pt; color: @TEXTO; }
QLabel#statTitulo { color: @SUAVE; font-size: 9pt; }

/* ---------- botones ---------- */
QPushButton { background: @TARJETA; border: 1px solid #cbd5e1; border-radius: 10px; padding: 8px 14px;
              min-height: 22px; font-weight: 600; }
QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { background: #f1f5f9; color: #a8b3c2; border-color: #e5eaf0; }
QPushButton#primario, QPushButton[destacado="true"] { background: @PRIMARIO; color: white; border: none;
              font-size: 11pt; min-height: 30px; padding: 10px 16px; border-radius: 12px; }
QPushButton#primario:hover, QPushButton[destacado="true"]:hover { background: @PRIMARIO_HOVER; }
QPushButton#primario:disabled { background: #b7d4d1; color: white; }
QPushButton#acento { background: @ACENTO; color: white; border: none; font-size: 12pt; min-height: 40px;
              padding: 12px 16px; border-radius: 14px; }
QPushButton#acento:hover { background: @ACENTO_HOVER; }
QPushButton#acento:disabled { background: #f5c4b9; color: white; }
QPushButton#acento[cancelar="true"] { background: #475569; }
QPushButton#acento[cancelar="true"]:hover { background: #334155; }
QPushButton#peligro { color: @PELIGRO; }
QPushButton#peligro:hover { background: #fef2f2; border-color: #fca5a5; }
QPushButton#reproducir { min-width: 118px; min-height: 26px; border-radius: 20px; background: @PRIMARIO; color: white;
              border: none; padding: 8px 18px; font-size: 10.5pt; }
QPushButton#reproducir:hover { background: @PRIMARIO_HOVER; }
QPushButton#reproducir:disabled { background: #b7d4d1; }
QPushButton#enlace { border: none; background: transparent; color: @PRIMARIO; text-align: left; padding: 4px 2px;
              min-height: 18px; }
QPushButton#enlace:hover { background: transparent; text-decoration: underline; }
QPushButton#enlace:disabled { color: #a8b3c2; background: transparent; }
QToolButton#desplegable { border: none; background: transparent; color: @SUAVE; font-weight: 600; padding: 4px 2px; }
QToolButton#desplegable:hover { color: @PRIMARIO; }

/* ---------- campos ---------- */
QLineEdit, QSpinBox, QComboBox { background: @TARJETA; border: 1px solid #cbd5e1; border-radius: 8px;
              padding: 6px 8px; min-height: 22px; selection-background-color: @PRIMARIO; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1.5px solid @PRIMARIO; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #f1f5f9; color: #a8b3c2; }
QSpinBox::up-button, QSpinBox::down-button { width: 20px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url(@ICO_ARRIBA); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url(@ICO_ABAJO); width: 10px; height: 10px; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url(@ICO_ABAJO); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: @TARJETA; border: 1px solid @BORDE; selection-background-color: @PRIMARIO_SUAVE;
              selection-color: @TEXTO; outline: 0; padding: 4px; }
QCheckBox { spacing: 8px; font-weight: 600; }
QCheckBox::indicator, QListView::indicator { width: 20px; height: 20px; border-radius: 6px; border: 2px solid #cbd5e1;
              background: @TARJETA; }
QCheckBox::indicator:hover, QListView::indicator:hover { border-color: @PRIMARIO; }
QCheckBox::indicator:checked, QListView::indicator:checked { background: @PRIMARIO; border-color: @PRIMARIO;
              image: url(@ICO_CHECK); }

/* ---------- lista de tubos ---------- */
QListWidget { background: @TARJETA; border: 1px solid @BORDE; border-radius: 10px; padding: 4px; outline: 0; }
QListWidget::item { padding: 8px 6px; border-radius: 8px; font-weight: 600; }
QListWidget::item:hover { background: #f1f5f9; }
QListWidget::item:selected { background: @PRIMARIO_SUAVE; color: @TEXTO; }

/* ---------- barra de reproducción / progreso ---------- */
QSlider::groove:horizontal { height: 6px; background: #e2e8f0; border-radius: 3px; }
QSlider::sub-page:horizontal { background: @PRIMARIO; border-radius: 3px; }
QSlider::handle:horizontal { background: white; border: 2px solid @PRIMARIO; width: 16px; height: 16px;
              margin: -7px 0; border-radius: 10px; }
QSlider::handle:horizontal:disabled { border-color: #cbd5e1; }
QSlider::sub-page:horizontal:disabled { background: #cbd5e1; }
QProgressBar { background: #e2e8f0; border: none; border-radius: 8px; min-height: 16px; max-height: 16px;
               text-align: center; color: @TEXTO; font-size: 9pt; font-weight: 600; }
QProgressBar::chunk { background: @ACENTO; border-radius: 8px; }

/* ---------- desplazamiento ---------- */
QScrollArea { border: none; background: transparent; }
QWidget#panelDer { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 4px; min-width: 30px; }

QLabel#firma { color: #cbd5e1; font-size: 8pt; font-weight: 700; padding: 0 10px; }
QLabel#firma:hover { color: @SUAVE; }

/* ---------- barra de estado ---------- */
QStatusBar { background: @TARJETA; border-top: 1px solid @BORDE; color: @SUAVE; }
QStatusBar::item { border: none; }

/* ---------- resultados: pestañas y tablas ---------- */
QTabWidget::pane { border: none; top: 4px; }
QTabBar::tab { background: transparent; color: @SUAVE; padding: 9px 16px; margin-right: 4px; border-radius: 10px;
              font-weight: 600; }
QTabBar::tab:hover { background: #e8edf3; }
QTabBar::tab:selected { background: @PRIMARIO; color: white; }
QTableWidget { background: @TARJETA; alternate-background-color: #f8fafc; border: 1px solid @BORDE;
              border-radius: 10px; gridline-color: transparent; outline: 0; }
QTableWidget::item { padding: 4px 6px; }
QTableWidget::item:selected { background: @PRIMARIO_SUAVE; color: @TEXTO; }
QHeaderView::section { background: #eef2f6; color: @SUAVE; border: none; padding: 8px 6px; font-weight: 700; }
QMessageBox QLabel { font-size: 10.5pt; }
QMessageBox QPushButton, QDialog QPushButton { min-width: 90px; }
"""


# ---------- iconos pequeños (flechas y palomita) que el QSS necesita como archivo ----------
def _iconos() -> dict[str, str]:
    carpeta = Path(tempfile.gettempdir()) / "tracker_gui_iconos"
    carpeta.mkdir(exist_ok=True)

    def hacer(nombre: str, color: str, puntos: list[tuple[float, float]], ancho: float, cerrado: bool) -> str:
        ruta = carpeta / f"{nombre}.png"
        pm = QPixmap(40, 40)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color), ancho)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        pol = QPolygonF([QPointF(x, y) for x, y in puntos])
        p.drawPolygon(pol) if cerrado else p.drawPolyline(pol)
        p.end()
        pm.save(str(ruta), "PNG")
        return ruta.as_posix()

    return {
        "ICO_CHECK": hacer("check", "#ffffff", [(9, 21), (17, 29), (31, 12)], 5, False),
        "ICO_ARRIBA": hacer("arriba", SUAVE, [(9, 26), (20, 14), (31, 26)], 4.5, False),
        "ICO_ABAJO": hacer("abajo", SUAVE, [(9, 14), (20, 26), (31, 14)], 4.5, False),
    }


def hoja_de_estilos() -> str:
    qss = QSS
    for k, v in {**_iconos(), **{
        "FONDO": FONDO, "TARJETA": TARJETA, "BORDE": BORDE, "TEXTO": TEXTO, "SUAVE": SUAVE,
        "PRIMARIO_SUAVE": PRIMARIO_SUAVE, "PRIMARIO_HOVER": PRIMARIO_HOVER, "PRIMARIO": PRIMARIO,
        "ACENTO_HOVER": ACENTO_HOVER, "ACENTO": ACENTO, "OK": OK, "PELIGRO": PELIGRO,
    }}.items():
        qss = qss.replace("@" + k, v)
    return qss


def aplicar(app: QApplication | None = None) -> str:
    """Estilo Fusion (igual en todos los sistemas) + hoja de estilos. Devuelve el QSS para `setStyleSheet`."""
    app = app or QApplication.instance()
    if app is not None:
        app.setStyle("Fusion")
    return hoja_de_estilos()


# ---------- componentes ----------
def repulir(w: QWidget) -> None:
    """Hace que Qt vuelva a leer las propiedades dinámicas (p. ej. [estado="hecho"]) del QSS."""
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def poner(w: QWidget, propiedad: str, valor) -> None:
    w.setProperty(propiedad, valor)
    repulir(w)


class Paso(QFrame):
    """Tarjeta de un paso: insignia numerada + título + ayuda. El contenido va en `.cuerpo` (QVBoxLayout)."""

    def __init__(self, numero: int, titulo: str, ayuda: str = "") -> None:
        super().__init__()
        self.setObjectName("tarjeta")
        self.numero = numero
        self.insignia = QLabel(str(numero))
        self.insignia.setObjectName("insignia")
        self.insignia.setAlignment(Qt.AlignCenter)
        self.titulo = QLabel(titulo)
        self.titulo.setObjectName("paso")
        cab = self.cab = QHBoxLayout()
        cab.setSpacing(10)
        cab.addWidget(self.insignia)
        cab.addWidget(self.titulo, 1)
        self.cuerpo = QVBoxLayout()
        self.cuerpo.setSpacing(10)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)
        lay.addLayout(cab)
        if ayuda:
            self.ayuda = QLabel(ayuda)
            self.ayuda.setObjectName("ayuda")
            self.ayuda.setWordWrap(True)
            lay.addWidget(self.ayuda)
        lay.addLayout(self.cuerpo)

    def titulo_con(self, widget: QWidget) -> None:
        """Variante compacta: el título se reemplaza por un widget (p. ej. el botón principal) en la misma fila."""
        self.titulo.hide()
        self.cab.addWidget(widget, 1)

    def estado(self, estado: str) -> None:
        """'pendiente' | 'activo' | 'hecho'."""
        self.insignia.setText("✓" if estado == "hecho" else str(self.numero))
        poner(self.insignia, "estado", {"activo": "activo", "hecho": "hecho"}.get(estado, "pendiente"))


class Desplegable(QWidget):
    """Sección que se abre/cierra con un clic (para dejar a la vista solo lo esencial)."""

    def __init__(self, titulo: str, abierto: bool = False) -> None:
        super().__init__()
        self.boton = QToolButton()
        self.boton.setObjectName("desplegable")
        self.boton.setText(" " + titulo)
        self.boton.setCheckable(True)
        self.boton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.boton.setCursor(Qt.PointingHandCursor)
        self.contenido = QWidget()
        self.cuerpo = QVBoxLayout(self.contenido)
        self.cuerpo.setContentsMargins(0, 4, 0, 0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.boton, 0, Qt.AlignLeft)
        lay.addWidget(self.contenido)
        self.boton.toggled.connect(self._cambio)
        self.boton.setChecked(abierto)
        self._cambio(abierto)

    def _cambio(self, abierto: bool) -> None:
        self.boton.setArrowType(Qt.DownArrow if abierto else Qt.RightArrow)
        self.contenido.setVisible(abierto)

    def abrir(self) -> None:
        self.boton.setChecked(True)