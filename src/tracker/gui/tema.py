"""Apariencia de la GUI: paleta, hoja de estilos (QSS) y pequeños componentes reutilizables.

Todo lo visual vive aquí para poder retocar colores/tamaños en un solo sitio. No contiene lógica del programa.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

# ---- paleta (galería blanca: fondo neutro, texto tinta, un solo azul para las acciones) ----
FONDO = "#f5f5f7"           # bruma de estudio: fondo de la ventana
TARJETA = "#ffffff"         # blanco galería: tarjetas y campos
BORDE = "#d6d6d6"           # línea fina plateada
CONTROL = "#e6e6e8"         # rellenos apagados y desactivados
TEXTO = "#1d1d1f"           # tinta
SUAVE = "#707070"           # texto secundario
ACERO = "#86868b"           # contornos de campos y botones secundarios
PRIMARIO = "#0071e3"        # azul de acción (botones rellenos)
PRIMARIO_HOVER = "#0077ed"
PRIMARIO_SUAVE = "#e8f1fc"
ENLACE = "#0066cc"          # azul de enlaces
ACENTO = PRIMARIO           # procesar: la acción principal usa el mismo azul
ACENTO_HOVER = PRIMARIO_HOVER
OK = "#1d8a3a"
PELIGRO = "#d70015"
VIDEO_FONDO = "#1d1d1f"

QSS = """
QWidget { font-family: ".AppleSystemUIFont", "Inter", "Helvetica Neue", "Segoe UI", Arial, sans-serif;
          font-size: 14px; color: @TEXTO; }
QMainWindow, QDialog, QWidget#raiz { background: @FONDO; }
QToolTip { background: @TARJETA; color: @TEXTO; border: 1px solid @BORDE; padding: 6px 10px; border-radius: 10px; }

/* ---------- tarjetas y encabezado (planas, sin sombra) ---------- */
QFrame#cabecera { background: @TARJETA; border: none; border-bottom: 1px solid @CONTROL; }
QLabel#titulo { font-size: 21px; font-weight: 600; color: @TEXTO; }
QLabel#subtitulo { color: @SUAVE; font-size: 12px; }
QLabel#chip { background: transparent; color: @TEXTO; border: 1px solid @ACERO; border-radius: 13px;
              padding: 4px 12px; font-size: 12px; }
QFrame#tarjeta { background: @TARJETA; border: none; border-radius: 24px; }
QFrame#tarjeta[inactiva="true"] { background: #fafafc; }
QFrame#interior { background: @FONDO; border: none; border-radius: 14px; }
QFrame#barra { background: @TARJETA; border: none; border-radius: 24px; }
QLabel#paso { font-size: 17px; font-weight: 600; }
QLabel#ayuda { color: @SUAVE; font-size: 12px; }
QLabel#guia { background: @TARJETA; color: @TEXTO; border-radius: 18px; padding: 12px 18px;
              font-size: 15px; font-weight: 500; }
QLabel#guia[estado="ok"] { color: @OK; }
QLabel#guia[estado="trabajando"] { color: @PRIMARIO; }
QLabel#nota { background: @FONDO; border-radius: 14px; padding: 10px 14px; color: @TEXTO; }
QLabel#resumen { font-weight: 500; color: @SUAVE; }
QLabel#insignia { min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; border-radius: 14px;
                  background: @CONTROL; color: @SUAVE; font-size: 13px; font-weight: 600; qproperty-alignment: AlignCenter; }
QLabel#insignia[estado="activo"] { background: @PRIMARIO; color: white; }
QLabel#insignia[estado="hecho"] { background: @TEXTO; color: white; }
QFrame#stat { background: @TARJETA; border: none; border-radius: 20px; }
QLabel#statValor { font-size: 28px; font-weight: 600; color: @TEXTO; }
QLabel#statValor[chico="true"] { font-size: 15px; color: @TEXTO; }
QLabel#statTitulo { color: @SUAVE; font-size: 12px; }
QFrame#hero { background: @TARJETA; border: none; border-radius: 28px; }
QFrame#hero QFrame#stat { background: @FONDO; }
QLabel#heroKicker { font-size: 17px; font-weight: 600; color: @TEXTO; }
QLabel#heroNumero { font-size: 80px; font-weight: 600; color: @TEXTO; letter-spacing: -1.2px; }
QLabel#heroLeyenda { font-size: 21px; color: @SUAVE; }

/* ---------- botones: píldoras; contorno para lo secundario, azul solo para la acción ---------- */
QPushButton { background: transparent; border: 1px solid @ACERO; border-radius: 17px; padding: 7px 16px;
              min-height: 18px; font-weight: 400; color: @TEXTO; }
QPushButton:hover { background: @FONDO; }
QPushButton:pressed { background: @CONTROL; }
QPushButton:disabled { background: transparent; color: #aeaeb2; border-color: @CONTROL; }
QPushButton#primario, QPushButton[destacado="true"] { background: @PRIMARIO; color: white; border: none;
              min-height: 22px; padding: 9px 18px; border-radius: 20px; }
QPushButton#primario:hover, QPushButton[destacado="true"]:hover { background: @PRIMARIO_HOVER; }
QPushButton#primario:disabled { background: @CONTROL; color: #aeaeb2; }
QPushButton#acento { background: @ACENTO; color: white; border: none; font-size: 17px; font-weight: 500;
              min-height: 26px; padding: 11px 20px; border-radius: 24px; }
QPushButton#acento:hover { background: @ACENTO_HOVER; }
QPushButton#acento:disabled { background: @CONTROL; color: #aeaeb2; }
QPushButton#acento[cancelar="true"] { background: @TEXTO; }
QPushButton#acento[cancelar="true"]:hover { background: #3a3a3c; }
QPushButton#peligro { color: @PELIGRO; border-color: @BORDE; }
QPushButton#peligro:hover { background: #fff2f3; }
QPushButton#reproducir { min-width: 118px; min-height: 22px; border-radius: 18px; background: rgba(210, 210, 215, 0.64);
              color: rgba(0, 0, 0, 0.8); border: none; padding: 7px 18px; }
QPushButton#reproducir:hover { background: rgba(200, 200, 205, 0.85); }
QPushButton#reproducir:disabled { background: @CONTROL; color: #aeaeb2; }
QPushButton#enlace { border: none; background: transparent; color: @ENLACE; text-align: left; padding: 4px 2px;
              min-height: 18px; }
QPushButton#enlace:hover { background: transparent; text-decoration: underline; }
QPushButton#enlace:disabled { color: #aeaeb2; background: transparent; }
QToolButton#desplegable { border: none; background: transparent; color: @ENLACE; padding: 4px 2px; }
QToolButton#desplegable:hover { text-decoration: underline; }

/* ---------- campos ---------- */
QLineEdit, QSpinBox, QComboBox { background: @TARJETA; border: 1px solid @ACERO; border-radius: 12px;
              padding: 6px 12px; min-height: 20px; selection-background-color: @PRIMARIO; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 2px solid @PRIMARIO; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: @FONDO; color: #aeaeb2; border-color: @CONTROL; }
QSpinBox::up-button, QSpinBox::down-button { width: 20px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url(@ICO_ARRIBA); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url(@ICO_ABAJO); width: 10px; height: 10px; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url(@ICO_ABAJO); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: @TARJETA; border: 1px solid @BORDE; selection-background-color: @FONDO;
              selection-color: @TEXTO; outline: 0; padding: 4px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator, QListView::indicator { width: 20px; height: 20px; border-radius: 10px; border: 1px solid @ACERO;
              background: @TARJETA; }
QCheckBox::indicator:hover, QListView::indicator:hover { border-color: @PRIMARIO; }
QCheckBox::indicator:checked, QListView::indicator:checked { background: @PRIMARIO; border-color: @PRIMARIO;
              image: url(@ICO_CHECK); }

/* ---------- lista de tubos ---------- */
QListWidget { background: @TARJETA; border: none; border-radius: 16px; padding: 4px; outline: 0; }
QListWidget::item { padding: 8px 6px; border-radius: 10px; }
QListWidget::item:hover { background: #fafafc; }
QListWidget::item:selected { background: @FONDO; color: @TEXTO; }

/* ---------- barra de reproducción / progreso ---------- */
QSlider::groove:horizontal { height: 4px; background: @CONTROL; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @TEXTO; border-radius: 2px; }
QSlider::handle:horizontal { background: white; border: 1px solid @BORDE; width: 18px; height: 18px;
              margin: -8px 0; border-radius: 10px; }
QSlider::sub-page:horizontal:disabled { background: @BORDE; }
QProgressBar { background: @CONTROL; border: none; border-radius: 4px; min-height: 8px; max-height: 8px;
               text-align: center; color: transparent; }
QProgressBar::chunk { background: @PRIMARIO; border-radius: 4px; }

/* ---------- desplazamiento ---------- */
QScrollArea { border: none; background: transparent; }
QWidget#panelDer { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(0, 0, 0, 0.18); border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(0, 0, 0, 0.32); }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:horizontal { background: rgba(0, 0, 0, 0.18); border-radius: 3px; min-width: 30px; }

QLabel#firma { color: @BORDE; font-size: 10px; font-weight: 600; padding: 0 10px; }
QLabel#firma:hover { color: @SUAVE; }

/* ---------- barra de estado ---------- */
QStatusBar { background: @FONDO; border-top: 1px solid @CONTROL; color: @SUAVE; font-size: 12px; }
QStatusBar::item { border: none; }

/* ---------- resultados: pestañas y tablas ---------- */
QTabWidget::pane { border: none; top: 6px; }
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab { background: transparent; color: @TEXTO; padding: 8px 18px; margin-right: 4px; border-radius: 16px; }
QTabBar::tab:hover { background: @CONTROL; }
QTabBar::tab:selected { background: @TEXTO; color: white; }
QTableWidget { background: @TARJETA; alternate-background-color: #fafafc; border: none;
              border-radius: 16px; gridline-color: transparent; outline: 0; }
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background: @FONDO; color: @TEXTO; }
QHeaderView::section { background: @TARJETA; color: @SUAVE; border: none; border-bottom: 1px solid @BORDE;
              padding: 8px 8px; font-size: 12px; font-weight: 500; }
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
        "ICO_ARRIBA": hacer("arriba", TEXTO, [(9, 26), (20, 14), (31, 26)], 4.5, False),
        "ICO_ABAJO": hacer("abajo", TEXTO, [(9, 14), (20, 26), (31, 14)], 4.5, False),
    }


def hoja_de_estilos() -> str:
    qss = QSS
    for k, v in {**_iconos(), **{
        "FONDO": FONDO, "TARJETA": TARJETA, "BORDE": BORDE, "CONTROL": CONTROL, "TEXTO": TEXTO, "SUAVE": SUAVE,
        "ACERO": ACERO, "ENLACE": ENLACE,
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