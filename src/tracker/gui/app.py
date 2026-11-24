from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import cv2
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from tracker.canales import Canal

from . import lineas, proceso, tema
from .canal_libre import CanalLibre, cargar_canales_libres, guardar_canales_libres
from .canvas import VideoCanvas, color_for, num_de
from .exportar_json import construir_documento, guardar_json, leer_json, nombre_secuencia
from .proceso import GPU_NO_SOPORTADA, HiloProceso, descripcion_modelo, nombre_modelo
from .resultados import ResultadosWindow

EJEMPLO = Path(__file__).resolve().parents[3] / "docs" / "ejemplo_formato"
MIN_GAP_PCT = 2  # separación mínima entre las líneas A y B (en %)
EXT_VIDEO = (".mp4", ".avi", ".mov", ".mkv")


def _punto_color(color: QColor) -> QIcon:
    """Circulito del color del tubo (para la lista)."""
    pm = QPixmap(28, 28)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawEllipse(3, 3, 22, 22)
    p.end()
    ic = QIcon(pm)
    ic.addPixmap(pm, QIcon.Selected)  # que no se desvanezca al elegir el tubo
    return ic


def _en_campo_de_texto() -> bool:
    return isinstance(QApplication.focusWidget(), (QLineEdit, QAbstractSpinBox))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tracker - Contador de salmones")
        self.setStyleSheet(tema.aplicar())
        self.setMinimumSize(1120, 680)
        pantalla = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1400, pantalla.width() - 40), min(880, pantalla.height() - 60))

        self.cap: cv2.VideoCapture | None = None
        self.video_path: Path | None = None
        self.frame_size: tuple[int, int] = (0, 0)
        self.channels: list[Canal] = []
        self._updating_list = False
        self._cfg_updating = False
        self.conteos: dict[str, int] = {}  # conteo por canal (en vivo y final)
        self.resultado = None  # tracker.pipeline.Resultados del último procesamiento
        self._exportado = False
        self.hilo: HiloProceso | None = None
        self.current = 0
        self.fps = 25.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self.canvas = VideoCanvas()
        self.canvas.channel_drawn.connect(self._on_channel_drawn)
        self.canvas.channel_clicked.connect(self._on_canvas_click)
        self.canvas.editing_changed.connect(self._on_editing_changed)
        self.canvas.channel_moving.connect(self._on_moving)
        self.canvas.channel_edited.connect(self._on_moving)
        self.canvas.message.connect(lambda m: self.statusBar().showMessage(m))
        self.canvas.drawing_changed.connect(self._on_drawing_changed)

        # ---- reproducción: solo Play y la barra ----
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.setMinimumHeight(26)
        self.slider.valueChanged.connect(self._show_frame)
        self.frame_label = QLabel("Cuadro: -")
        self.frame_label.setObjectName("ayuda")
        self.frame_label.setMinimumWidth(110)
        self.btn_play = QPushButton("▶ Reproducir")
        self.btn_play.setObjectName("reproducir")
        self.btn_play.setToolTip("Reproducir / pausar (Espacio)")
        self.btn_play.setFocusPolicy(Qt.NoFocus)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_play)

        barra_play = QFrame()
        barra_play.setObjectName("barra")
        row = QHBoxLayout(barra_play)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(14)
        row.addWidget(self.btn_play)
        row.addWidget(self.slider, 1)
        row.addWidget(self.frame_label)

        # guía: siempre dice qué hacer ahora
        self.lbl_guia = QLabel()
        self.lbl_guia.setObjectName("guia")
        self.lbl_guia.setWordWrap(True)

        self.left_widget = QWidget()
        left = QVBoxLayout(self.left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(12)
        left.addWidget(self.lbl_guia)
        left.addWidget(self.canvas, 1)
        left.addWidget(barra_play)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._atajo_play)
        QShortcut(QKeySequence(Qt.Key_Delete), self, activated=self._atajo_eliminar)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self.on_enter)
        QShortcut(QKeySequence(Qt.Key_Enter), self, activated=self.on_enter)

        # ================= panel derecho: 4 pasos =================
        # ---- Paso 1: abrir el video ----
        self.paso1 = tema.Paso(1, "Abre tu video")
        self.btn_open = QPushButton("Abrir video…")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.setToolTip("Elige un video, o arrástralo directamente a esta ventana")
        self.btn_open.clicked.connect(self.open_video)
        self.lbl_video = QLabel("Ningún video abierto")
        self.lbl_video.setObjectName("resumen")
        self.lbl_video.setWordWrap(True)
        self.paso1.cuerpo.addWidget(self.btn_open)
        self.paso1.cuerpo.addWidget(self.lbl_video)

        # ---- Paso 2: marcar los tubos ----
        self.paso2 = tema.Paso(2, "Marca los tubos")
        self.btn_draw = QPushButton("＋  Dibujar tubo")
        self.btn_draw.setObjectName("primario")
        self.btn_draw.setCursor(Qt.PointingHandCursor)
        self.btn_draw.setToolTip("Arrastra el mouse sobre el video")
        self.btn_draw.clicked.connect(self.start_drawing)
        self.list = QListWidget()
        self.list.setIconSize(QSize(14, 14))
        self.list.setMinimumHeight(96)
        self.list.setMaximumHeight(170)
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.installEventFilter(self)  # la lista conserva Espacio y flechas
        self.lbl_lista = QLabel("Tubos (✔ = se analiza). Clic en un tubo del video para configurarlo:")
        self.lbl_lista.setObjectName("ayuda")
        self.lbl_lista.setWordWrap(True)
        self.lbl_vacio = QLabel("Todavía no hay tubos.\nPulsa «Dibujar tubo» y arrastra sobre el video.")
        self.lbl_vacio.setObjectName("ayuda")
        self.lbl_vacio.setAlignment(Qt.AlignCenter)
        self.lbl_vacio.setMinimumHeight(70)
        self.list.setVisible(False)  # se muestran al haber tubos (ver _refresh_list)
        self.lbl_lista.setVisible(False)

        self.btn_done = QPushButton("✔ Listo (Enter)")
        self.btn_done.setToolTip("Fija el tubo para no moverlo por accidente")
        self.btn_done.setCursor(Qt.PointingHandCursor)
        self.btn_done.clicked.connect(lambda: self.canvas.set_editing(None))
        self.btn_done.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar tubo (Supr)")
        self.btn_delete.setObjectName("peligro")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.clicked.connect(self.delete_channel)
        fila_tubo = QHBoxLayout()
        fila_tubo.setSpacing(8)
        fila_tubo.addWidget(self.btn_done, 1)
        fila_tubo.addWidget(self.btn_delete, 1)

        # configuración del tubo seleccionado (se abre al hacer clic sobre un tubo)
        self.ed_nombre = QLineEdit()
        self.ed_nombre.editingFinished.connect(self._on_nombre)
        self.chk_activo = QCheckBox("Analizar este tubo")
        self.chk_activo.toggled.connect(self._on_activo)
        self.sp_a = QSpinBox(); self.sp_b = QSpinBox()
        for sp in (self.sp_a, self.sp_b):
            sp.setRange(0, 100); sp.setSuffix(" %")
        self.sp_x = QSpinBox(); self.sp_y = QSpinBox()
        self.sp_w = QSpinBox(); self.sp_h = QSpinBox()
        for sp in (self.sp_x, self.sp_y, self.sp_w, self.sp_h):
            sp.setRange(0, 99999); sp.setSuffix(" px")
        self.sp_a.valueChanged.connect(self._on_linea_a)
        self.sp_b.valueChanged.connect(self._on_linea_b)
        for sp in (self.sp_x, self.sp_y, self.sp_w, self.sp_h):
            sp.valueChanged.connect(self._on_geom)
        for sp in (self.sp_a, self.sp_b, self.sp_x, self.sp_y, self.sp_w, self.sp_h):
            sp.setKeyboardTracking(False)  # aplica al terminar de escribir
        self.btn_reset_lineas = QPushButton(f"Restablecer líneas A/B ({lineas.LINEA_A:.0%} / {lineas.LINEA_B:.0%})")
        self.btn_reset_lineas.setToolTip("Vuelve a la posición recomendada de las líneas (lineas.py): el pez cuenta si se\n"
                                         "ve sobre A y después llega a B. Muy arriba o muy abajo se pierden peces.")
        self.btn_reset_lineas.setCursor(Qt.PointingHandCursor)
        self.btn_reset_lineas.clicked.connect(self._on_reset_lineas)

        tit_cfg = QLabel("Ajustes del tubo seleccionado")
        tit_cfg.setObjectName("paso")
        lab_nombre = QLabel("Nombre")
        lab_a = QLabel("Línea A (entrada)" + ("" if lineas.EDITABLES else " · fija"))
        lab_b = QLabel("Línea B (salida)" + ("" if lineas.EDITABLES else " · fija"))
        for lab in (lab_nombre, lab_a, lab_b):
            lab.setObjectName("ayuda")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        grid.addWidget(lab_nombre, 0, 0, 1, 2)
        grid.addWidget(self.ed_nombre, 1, 0, 1, 2)
        grid.addWidget(lab_a, 2, 0)
        grid.addWidget(lab_b, 2, 1)
        grid.addWidget(self.sp_a, 3, 0)
        grid.addWidget(self.sp_b, 3, 1)

        # posición y tamaño: se dejan a mano pero plegados 
        self.avanzado_tubo = tema.Desplegable("Posición y tamaño (avanzado)")
        g2 = QGridLayout()
        g2.setHorizontalSpacing(10)
        g2.setVerticalSpacing(4)
        for i, (txt, sp) in enumerate((("X", self.sp_x), ("Y", self.sp_y), ("Ancho", self.sp_w), ("Alto", self.sp_h))):
            lab = QLabel(txt)
            lab.setObjectName("ayuda")
            g2.addWidget(lab, (i // 2) * 2, i % 2)
            g2.addWidget(sp, (i // 2) * 2 + 1, i % 2)
        self.avanzado_tubo.cuerpo.addLayout(g2)

        self.cfg = QFrame()
        self.cfg.setObjectName("interior")
        cl = QVBoxLayout(self.cfg)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(10)
        cl.addWidget(tit_cfg)
        cl.addLayout(grid)
        cl.addWidget(self.chk_activo)
        cl.addWidget(self.btn_reset_lineas)
        cl.addWidget(self.avanzado_tubo)
        self._cfg_widgets = [self.ed_nombre, self.chk_activo, self.sp_a, self.sp_b, self.btn_reset_lineas,
                             self.sp_x, self.sp_y, self.sp_w, self.sp_h]

        self.btn_save = QPushButton("Guardar tubos…")
        self.btn_save.setToolTip("Guarda los tubos en un archivo (.canales.json) para reutilizarlos")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save)
        self.btn_load = QPushButton("Cargar tubos…")
        self.btn_load.setToolTip("Carga tubos guardados antes para este mismo video")
        self.btn_load.setCursor(Qt.PointingHandCursor)
        self.btn_load.clicked.connect(self.load)
        fila_arch = QHBoxLayout()
        fila_arch.setSpacing(8)
        fila_arch.addWidget(self.btn_save, 1)
        fila_arch.addWidget(self.btn_load, 1)

        self.paso2.cuerpo.addWidget(self.btn_draw)
        self.paso2.cuerpo.addWidget(self.lbl_lista)
        self.paso2.cuerpo.addWidget(self.list)
        self.paso2.cuerpo.addWidget(self.lbl_vacio)
        self.paso2.cuerpo.addLayout(fila_tubo)
        self.paso2.cuerpo.addWidget(self.cfg)
        self.paso2.cuerpo.addLayout(fila_arch)

        # ---- Paso 3: procesar ----
        self.paso3 = tema.Paso(3, "Cuenta los peces")
        self.btn_proc = QPushButton("⚙  Procesar video")
        self.btn_proc.setObjectName("acento")
        self.btn_proc.setCursor(Qt.PointingHandCursor)
        self.btn_proc.setToolTip("Detecta, sigue y cuenta los peces de los tubos marcados (✔)")
        self.btn_proc.clicked.connect(self.toggle_proceso)
        self.progreso = QProgressBar()
        self.progreso.setVisible(False)
        self.lbl_modelo = QLabel(f"Modelo: {nombre_modelo()}")
        self.lbl_modelo.setObjectName("chip")
        self.lbl_modelo.setToolTip(f"{descripcion_modelo()}\nPerfil '{proceso.PERFIL}' "
                                   f"(configs/perfiles/{proceso.PERFIL}.yaml)")
        self.cb_disp = QComboBox()
        self.cb_disp.addItems(["Automático (GPU si sirve)", "CPU"])
        self.cb_disp.setToolTip("Si tu GPU es antigua y falla, elige CPU (más lento)")
        self.paso3.titulo_con(self.btn_proc)  # compacto: número del paso + botón grande en una sola fila
        self.paso3.cuerpo.addWidget(self.progreso)
        self.paso3.cuerpo.setSpacing(0)

        # ---- Paso 4: resultados ----
        self.paso4 = tema.Paso(4, "Revisa y exporta")
        self.lbl_resumen = QLabel("Aún no hay resultados.")
        self.lbl_resumen.setObjectName("resumen")
        self.lbl_resumen.setWordWrap(True)
        self.btn_ver = QPushButton("Ver resultados")
        self.btn_ver.setCursor(Qt.PointingHandCursor)
        self.btn_ver.setToolTip("Muestra el último procesamiento; si no hay uno, deja abrir un JSON de resultados "
                                "exportado")
        self.btn_ver.clicked.connect(self.ver_resultado)
        self.btn_exportar = QPushButton("Exportar resultados…")
        self.btn_exportar.setObjectName("primario")
        self.btn_exportar.setCursor(Qt.PointingHandCursor)
        self.btn_exportar.setToolTip("Guarda UN archivo JSON con la secuencia, los tubos, el conteo y, cuadro por cuadro, "
                                     "las cajas del seguimiento con su ID")
        self.btn_exportar.setEnabled(False)
        self.btn_exportar.clicked.connect(self.exportar)
        fila_res = QHBoxLayout()
        fila_res.setSpacing(8)
        fila_res.addWidget(self.btn_exportar, 3)
        fila_res.addWidget(self.btn_ver, 2)
        self.paso4.cuerpo.addWidget(self.lbl_resumen)
        self.paso4.cuerpo.addLayout(fila_res)

        panel = QWidget()
        panel.setObjectName("panelDer")
        right = QVBoxLayout(panel)
        right.setContentsMargins(0, 0, 6, 0)
        right.setSpacing(12)
        right.addWidget(self.paso1)
        right.addWidget(self.paso2)
        right.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(panel)
        fijos = QWidget()  # los pasos 3 y 4 siempre quedan a la vista, sin tener que desplazarse
        fijos.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        fl = QVBoxLayout(fijos)
        fl.setContentsMargins(0, 0, 6, 0)
        fl.setSpacing(12)
        fl.addWidget(self.paso3)
        fl.addWidget(self.paso4)
        side = QWidget()
        side.setFixedWidth(400)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(12)
        sl.addWidget(scroll, 1)
        sl.addWidget(fijos)

        # ---- cabecera ----
        titulo = QLabel("Contador de salmones")
        titulo.setObjectName("titulo")
        sub = QLabel("Sigue los 4 pasos de la derecha")
        sub.setObjectName("subtitulo")
        cab = QFrame()
        cab.setObjectName("cabecera")
        hl = QHBoxLayout(cab)
        hl.setContentsMargins(20, 12, 20, 12)
        hl.setSpacing(14)
        hl.addWidget(titulo)
        hl.addWidget(sub)
        hl.addStretch(1)
        lab_disp = QLabel("Dispositivo")
        lab_disp.setObjectName("subtitulo")
        self.cb_disp.setMinimumWidth(210)
        hl.addWidget(lab_disp)
        hl.addWidget(self.cb_disp)
        hl.addWidget(self.lbl_modelo)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(16, 14, 10, 14)
        cuerpo.setSpacing(16)
        cuerpo.addWidget(self.left_widget, 1)
        cuerpo.addWidget(side)
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(cab)
        root.addLayout(cuerpo, 1)
        central = QWidget()
        central.setObjectName("raiz")
        central.setLayout(root)
        self.setCentralWidget(central)
        self.setAcceptDrops(True)  # arrastrar un video a la ventana lo abre

        self.canvas.open_requested.connect(self.open_video)
        self.res_win = None
        self._load_cfg()
        self._actualizar_guia()
        firma = QLabel("AV")  # iniciales, discretas en la esquina
        firma.setObjectName("firma")
        self.statusBar().addPermanentWidget(firma)
        self.statusBar().showMessage("Abre un video para comenzar.")

    # ---- guía de pasos ----
    def _actualizar_guia(self) -> None:
        """Marca el paso en el que está la persona y le dice qué hacer ahora."""
        hay_video = self.cap is not None
        hay_tubos = bool(self.selected_channels())
        corriendo = self.hilo is not None
        hecho = self.resultado is not None

        def est(listo: bool, activo: bool) -> str:
            return "hecho" if listo else ("activo" if activo else "pendiente")

        self.paso1.estado(est(hay_video, not hay_video))
        self.paso2.estado(est(hay_tubos, hay_video))
        self.paso3.estado(est(hecho, hay_video and hay_tubos))
        self.paso4.estado(est(self._exportado, hecho))
        tema.poner(self.btn_open, "destacado", not hay_video)
        self.btn_draw.setEnabled(hay_video and not self.canvas.is_drawing)

        estado = ""
        if corriendo:
            texto, estado = "Contando peces… puedes cancelar cuando quieras.", "trabajando"
        elif not hay_video:
            texto = "Para empezar, abre el video que quieres analizar (paso 1)."
        elif self.canvas.is_drawing:
            texto = "Arrastra el mouse sobre el video para dibujar el tubo. Esc cancela."
        elif not self.channels:
            texto = "Paso 2: pulsa «Dibujar tubo» y marca cada tubo sobre el video."
        elif not hay_tubos:
            texto = "Marca con ✔ al menos un tubo de la lista para poder analizarlo."
        elif self._exportado:
            texto, estado = "Resultados exportados ✔  Puedes abrir otro video cuando quieras.", "ok"
        elif hecho:
            texto, estado = "¡Listo! Paso 4: revisa los resultados y expórtalos.", "ok"
        else:
            texto = "Paso 3: cuando los tubos estén bien marcados, pulsa «Procesar video»."
        self.lbl_guia.setText(texto)
        tema.poner(self.lbl_guia, "estado", estado)

    # ---- arrastrar un video a la ventana ----
    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if self.hilo is None and urls and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith(EXT_VIDEO):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        self.load_video(event.mimeData().urls()[0].toLocalFile())

    def eventFilter(self, obj, event) -> bool:
        if obj is self.list and event.type() == QEvent.ShortcutOverride \
                and event.key() in (Qt.Key_Space, Qt.Key_Left, Qt.Key_Right):
            event.accept()  # evita que el atajo de la ventana consuma la tecla
            return True
        return super().eventFilter(obj, event)

    def _confirm_discard(self, accion: str) -> bool:
        """Pide confirmación si hay tubos que se perderían."""
        if not self.channels:
            return True
        r = QMessageBox.question(
            self, "Descartar tubos",
            f"Hay {len(self.channels)} tubo(s) que se perderán si no los guardaste.\n¿{accion}?",
        )
        return r == QMessageBox.Yes

    # ---- API para integración ----
    def selected_channels(self) -> list[Canal]:
        """Canales marcados para analizar (activo=True)."""
        return [c for c in self.channels if c.activo]

    # ---- video ----
    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir video", "", "Videos (*.mp4 *.avi *.mov *.mkv);;Todos (*)"
        )
        if path:
            self.load_video(path)

    def load_video(self, path: str) -> bool:
        cap = cv2.VideoCapture(path)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        if not ok:
            cap.release()
            QMessageBox.critical(
                self, "Video inválido",
                f"No se pudo abrir o leer el video:\n{path}\n\nVerifica que el archivo exista y sea un video válido.",
            )
            return False
        if not self._confirm_discard("Abrir el video de todos modos") or not self._confirm_resultado():
            cap.release()
            return False
        self.pause()
        self.canvas.cancel_drawing()
        if self.cap is not None:
            self.cap.release()
        self.cap, self.video_path = cap, Path(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 25.0
        h, w = frame.shape[:2]
        self.frame_size = (w, h)
        self.sp_x.setRange(0, w); self.sp_y.setRange(0, h)
        self.sp_w.setRange(5, w); self.sp_h.setRange(5, h)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.canvas.set_editing(None)
        self.channels = []
        self._reset_resultados()
        self._refresh_list()
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(n - 1, 0))
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.slider.setEnabled(n > 1)
        self.btn_play.setEnabled(n > 1)
        self.current = 0
        self._display(frame, 0, n)
        self.lbl_video.setText(f"{self.video_path.name}\n{w}×{h} · {n} cuadros")
        self.statusBar().showMessage(f"{self.video_path.name}: {w}x{h}, {n} cuadros.")
        self._actualizar_guia()
        return True

    def _show_frame(self, idx: int) -> None:
        if self.cap is None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self.cap.read()
        if ok:
            self.current = idx
            self._display(frame, idx, self.slider.maximum() + 1)

    @staticmethod
    def _a_qimage(frame) -> QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()

    def _display(self, frame, idx: int, total) -> None:
        self.canvas.clear_overlay()  # las cajas son de un cuadro procesado; al navegar ya no corresponden
        self.canvas.set_frame(self._a_qimage(frame))
        self.frame_label.setText(f"Cuadro: {idx + 1}/{total}")

    # ---- reproducción ----
    @property
    def playing(self) -> bool:
        return self.timer.isActive()

    def toggle_play(self) -> None:
        if self.cap is None:
            return
        if self.playing:
            self.pause()
        else:
            if self.current >= self.slider.maximum():
                self.slider.setValue(0)
            self.timer.start(int(1000 / self.fps))
            self.btn_play.setText("⏸ Pausa")

    def pause(self) -> None:
        self.timer.stop()
        self.btn_play.setText("▶ Reproducir")

    def _tick(self) -> None:
        ok, frame = self.cap.read()
        if not ok:
            self.pause()
            return
        self.current += 1
        self.slider.blockSignals(True)
        self.slider.setValue(self.current)
        self.slider.blockSignals(False)
        self._display(frame, self.current, self.slider.maximum() + 1)
        if self.current >= self.slider.maximum():
            self.pause()

    def _atajo_play(self) -> None:
        if not _en_campo_de_texto():
            self.toggle_play()

    def _atajo_eliminar(self) -> None:
        if not _en_campo_de_texto():
            self.delete_channel()

    def start_drawing(self) -> None:
        self.pause()
        self.canvas.start_drawing()

    # ---- canales ----
    def _on_drawing_changed(self, drawing: bool) -> None:
        self.btn_draw.setEnabled(not drawing and self.cap is not None)
        self._actualizar_guia()

    def _on_channel_drawn(self, caja: tuple) -> None:
        n = max((num_de(c.id) for c in self.channels), default=0) + 1
        self.channels.append(CanalLibre(f"canal_{n}", caja, f"Tubo {n}", linea_a=lineas.LINEA_A, linea_b=lineas.LINEA_B))
        self._refresh_list(keep_row=len(self.channels) - 1)
        self.canvas.set_editing(f"canal_{n}")  # el tubo nuevo queda editable
        self.statusBar().showMessage(
            f"Tubo {n} creado. Mueve sus 4 esquinas (Mayús = solo cambiar el tamaño) o usa el panel. "
            f"Las líneas A/B parten en {lineas.LINEA_A:.0%} / {lineas.LINEA_B:.0%}. Cuando esté listo, Enter o clic fuera."
        )

    def _on_canvas_click(self, channel_id: str) -> None:
        for row, c in enumerate(self.channels):
            if c.id == channel_id:
                self.list.setCurrentRow(row)
                return

    def _refresh_list(self, keep_row: int = -1) -> None:
        self._updating_list = True
        self.list.clear()
        for c in self.channels:
            item = QListWidgetItem(self._item_texto(c))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if c.activo else Qt.Unchecked)
            item.setIcon(_punto_color(color_for(c.id)))
            item.setSizeHint(QSize(0, 38))
            self.list.addItem(item)
        self._updating_list = False
        if self.channels and keep_row >= 0:
            self.list.setCurrentRow(min(keep_row, len(self.channels) - 1))
        self.canvas.set_channels(self.channels)
        self.list.setVisible(bool(self.channels))
        self.lbl_lista.setVisible(bool(self.channels))
        self.lbl_vacio.setVisible(not self.channels)
        self._sync_active()
        self._actualizar_guia()

    def _item_texto(self, c: Canal) -> str:
        n = self.conteos.get(c.id)
        return f"{c.nombre or c.id}  ·  {n}" if (c.activo and n is not None) else (c.nombre or c.id)

    def _push_conteos(self) -> None:
        """Refleja self.conteos en el video y en la lista de tubos."""
        self.canvas.set_conteos(self.conteos)
        self._updating_list = True
        for i, c in enumerate(self.channels):
            if i < self.list.count():
                self.list.item(i).setText(self._item_texto(c))
        self._updating_list = False

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating_list:
            return
        row = self.list.row(item)
        self.list.setCurrentRow(row)
        self.channels[row].activo = item.checkState() == Qt.Checked
        self.canvas.set_channels(self.channels)
        self._load_cfg()
        self._actualizar_guia()

    def _on_row_changed(self, _row: int) -> None:
        if not self._updating_list:
            self._sync_active()

    def _current_channel(self) -> Canal | None:
        row = self.list.currentRow()
        return self.channels[row] if 0 <= row < len(self.channels) else None

    def _sync_active(self) -> None:
        ch = self._current_channel()
        active = ch.id if ch else None
        self.canvas.set_active(active)
        if self.canvas.editing_id is not None and self.canvas.editing_id != active:
            self.canvas.set_editing(None)  # al elegir otro tubo, el anterior se fija
        self._load_cfg()
        self.btn_done.setEnabled(self.canvas.editing_id is not None)

    def on_enter(self) -> None:
        if _en_campo_de_texto():
            QApplication.focusWidget().clearFocus()  # confirma el valor que se estaba escribiendo
        elif not self.canvas.is_drawing and self.canvas.editing_id is not None:
            self.canvas.set_editing(None)

    def _on_editing_changed(self, channel_id: str) -> None:
        self.btn_done.setEnabled(channel_id != "")
        if channel_id == "":
            self.statusBar().showMessage("Tubo fijado. Haz clic sobre él para configurarlo de nuevo.")
        else:
            self.statusBar().showMessage("Configurando el tubo: arrastra las 4 esquinas (Mayús = solo tamaño), las "
                                         "líneas A/B, o usa el panel. Enter o clic fuera para fijar.")

    def delete_channel(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            self.statusBar().showMessage("Haz clic en un tubo (en el video o en la lista) y luego Eliminar.")
            return
        name = self.channels[row].nombre
        if QMessageBox.question(self, "Eliminar tubo", f"¿Eliminar '{name}'?") != QMessageBox.Yes:
            return
        del self.channels[row]
        self._refresh_list(keep_row=row)
        self.statusBar().showMessage(f"'{name}' eliminado.")

    # ---- panel de configuración del tubo ----
    def _load_cfg(self) -> None:
        ch = self._current_channel()
        self._cfg_updating = True
        self.cfg.setVisible(ch is not None)
        for w in self._cfg_widgets:
            w.setEnabled(ch is not None)
        if not lineas.EDITABLES:  # las líneas A y B se ven, pero no se editan
            self.sp_a.setEnabled(False)
            self.sp_b.setEnabled(False)
            self.btn_reset_lineas.setEnabled(False)
        if ch is None:
            self.ed_nombre.clear()
            self.chk_activo.setChecked(False)
        else:
            x1, y1, x2, y2 = ch.caja
            self.ed_nombre.setText(ch.nombre)
            self.chk_activo.setChecked(ch.activo)
            self.sp_a.setValue(round(ch.linea_a * 100))
            self.sp_b.setValue(round(ch.linea_b * 100))
            self.sp_x.setValue(round(x1))
            self.sp_y.setValue(round(y1))
            self.sp_w.setValue(round(x2 - x1))
            self.sp_h.setValue(round(y2 - y1))
        self._cfg_updating = False

    def _on_moving(self, channel_id: str) -> None:
        ch = self._current_channel()
        if ch is not None and ch.id == channel_id:
            self._load_cfg()

    def _on_nombre(self) -> None:
        ch = self._current_channel()
        if self._cfg_updating or ch is None:
            return
        nombre = self.ed_nombre.text().strip()
        if not nombre:
            self._load_cfg()
            return
        ch.nombre = nombre
        self._updating_list = True
        self.list.item(self.list.currentRow()).setText(self._item_texto(ch))
        self._updating_list = False
        self.canvas.update()

    def _on_activo(self, checked: bool) -> None:
        ch = self._current_channel()
        if self._cfg_updating or ch is None:
            return
        ch.activo = checked
        self._updating_list = True
        self.list.item(self.list.currentRow()).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._updating_list = False
        self.canvas.update()
        self._actualizar_guia()

    def _on_linea_a(self, v: int) -> None:
        ch = self._current_channel()
        if self._cfg_updating or ch is None or not lineas.EDITABLES:
            return
        if v > round(ch.linea_b * 100) - MIN_GAP_PCT:
            self.statusBar().showMessage("La línea A debe quedar arriba de la B.")
        else:
            ch.linea_a = v / 100
        self._load_cfg()
        self.canvas.update()

    def _on_linea_b(self, v: int) -> None:
        ch = self._current_channel()
        if self._cfg_updating or ch is None or not lineas.EDITABLES:
            return
        if v < round(ch.linea_a * 100) + MIN_GAP_PCT:
            self.statusBar().showMessage("La línea B debe quedar debajo de la A.")
        else:
            ch.linea_b = v / 100
        self._load_cfg()
        self.canvas.update()

    def _on_reset_lineas(self) -> None:
        ch = self._current_channel()
        if self._cfg_updating or ch is None or not lineas.EDITABLES:
            return
        ch.linea_a, ch.linea_b = lineas.LINEA_A, lineas.LINEA_B
        self._load_cfg()
        self.canvas.update()
        self.statusBar().showMessage(f"Líneas de '{ch.nombre or ch.id}' restablecidas a "
                                     f"{lineas.LINEA_A:.0%} / {lineas.LINEA_B:.0%}.")

    def _on_geom(self) -> None:
        ch = self._current_channel()
        if self._cfg_updating or ch is None:
            return
        iw, ih = self.frame_size
        x, y, w, h = self.sp_x.value(), self.sp_y.value(), self.sp_w.value(), self.sp_h.value()
        x2, y2 = min(x + w, iw), min(y + h, ih)
        if x2 - x < 5 or y2 - y < 5:
            self.statusBar().showMessage("El tubo quedaría fuera del video o demasiado pequeño.")
        else:
            ch.set_caja(float(x), float(y), float(x2), float(y2))  # conserva la forma del tubo
        self._load_cfg()
        self.canvas.update()

    # ---- guardar / cargar (formato común: tracker.canales) ----
    def save(self) -> None:
        if self.video_path is None:
            QMessageBox.warning(self, "Sin video", "Abre un video antes de guardar los canales.")
            return
        if not self.channels:
            QMessageBox.warning(self, "Sin tubos", "No hay tubos marcados. Dibuja al menos uno.")
            return
        if not self.selected_channels():
            r = QMessageBox.question(
                self, "Ningún tubo seleccionado",
                "Ningún tubo está marcado para analizar (✔). El procesamiento exige al menos uno.\n"
                "¿Guardar de todos modos?",
            )
            if r != QMessageBox.Yes:
                return
        default = str(self.video_path.with_suffix(".canales.json"))
        path, _ = QFileDialog.getSaveFileName(self, "Guardar canales", default, "JSON (*.json)")
        if path:
            self.save_to(path)

    def save_to(self, path: str) -> bool:
        try:
            guardar_canales_libres(path, self.channels, self.video_path.name, *self.frame_size)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Error al guardar", str(e))
            return False
        self.statusBar().showMessage(
            f"Guardado: {len(self.channels)} tubos ({len(self.selected_channels())} para analizar) en {path}"
        )
        return True

    def load(self) -> None:
        if self.video_path is None:
            QMessageBox.warning(self, "Sin video", "Abre primero el video al que corresponden los canales.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Cargar canales", "", "JSON (*.json)")
        if path:
            self.load_from(path)

    def load_from(self, path: str) -> bool:
        try:
            video = json.loads(Path(path).read_text(encoding="utf-8")).get("video") or {}
            channels = cargar_canales_libres(path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            QMessageBox.critical(self, "Archivo inválido", f"No se pudieron leer los canales:\n{e}")
            return False
        size = (video.get("ancho"), video.get("alto"))
        if all(size) and tuple(size) != self.frame_size:
            QMessageBox.warning(
                self, "Resolución distinta",
                f"Los canales se marcaron en un video de {size[0]}x{size[1]} y el actual es "
                f"{self.frame_size[0]}x{self.frame_size[1]}. No se cargaron.",
            )
            return False
        if not self._confirm_discard("Cargar los canales del archivo"):
            return False
        self.canvas.set_editing(None)
        self.channels = channels
        self._refresh_list()
        aviso = ""
        fuera = [c for c in channels if lineas.fuera_de_rango(c.linea_a, c.linea_b)]
        if fuera and lineas.EDITABLES:
            detalle = "\n".join(f"  • {c.nombre or c.id}: A {c.linea_a:.0%} / B {c.linea_b:.0%}" for c in fuera)
            r = QMessageBox.question(
                self, "Líneas A/B fuera de rango",
                f"Estos tubos traen líneas donde el conteo suele perder peces:\n{detalle}\n\n"
                "Si A queda muy arriba, los peces que se detectan más abajo no cuentan; si B queda muy abajo, "
                f"los que terminan antes tampoco.\n¿Usar las recomendadas ({lineas.LINEA_A:.0%} / {lineas.LINEA_B:.0%})?")
            if r == QMessageBox.Yes:
                for c in fuera:
                    c.linea_a, c.linea_b = lineas.LINEA_A, lineas.LINEA_B
                self._load_cfg()
                self.canvas.update()
                aviso = " Líneas A/B restablecidas a las recomendadas."
        elif not lineas.EDITABLES and any(abs(c.linea_a - lineas.LINEA_A) > 0.005 or abs(c.linea_b - lineas.LINEA_B) > 0.005
                                          for c in channels):
            aviso = " Traen sus propias líneas A/B: se respetan tal cual y no se pueden editar."
        self.statusBar().showMessage(f"Cargados {len(channels)} tubos.{aviso}")
        return True

    # ---- procesamiento en vivo (T15) ----
    def _reset_resultados(self) -> None:
        self.conteos = {}
        self.resultado = None
        self._exportado = False
        self.btn_exportar.setEnabled(False)
        self.lbl_resumen.setText("Aún no hay resultados.")
        self.canvas.clear_overlay()
        self.canvas.set_conteos({})

    def _confirm_resultado(self) -> bool:
        """Avisa si hay un resultado procesado que todavía no se exportó."""
        if self.resultado is None or self._exportado:
            return True
        r = QMessageBox.question(
            self, "Resultado sin exportar",
            "Hay un resultado procesado que no se ha exportado y se perderá.\n¿Continuar de todos modos?",
        )
        return r == QMessageBox.Yes

    def toggle_proceso(self) -> None:
        if self.hilo is not None:  # ya está corriendo: cancelar
            self.hilo.cancelar()
            self.btn_proc.setEnabled(False)
            self.statusBar().showMessage("Cancelando…")
            return
        self.iniciar_proceso()

    def iniciar_proceso(self) -> bool:
        if self.video_path is None:
            QMessageBox.warning(self, "Sin video", "Abre un video antes de procesar.")
            return False
        if not self.channels:
            QMessageBox.warning(self, "Sin tubos", "Dibuja al menos un tubo sobre el video antes de procesar.")
            return False
        if not self.selected_channels():
            QMessageBox.warning(self, "Ningún tubo seleccionado",
                                "Marca (✔) al menos un tubo para analizar. Los tubos sin marcar se ignoran.")
            return False
        if not self._confirmar_lineas():
            return False
        if not self._confirm_resultado():
            return False
        self.canvas.set_editing(None)
        self.pause()
        perfil = proceso.PERFIL
        self.resultado, self._exportado = None, False
        self.btn_exportar.setEnabled(False)
        self.conteos = {c.id: 0 for c in self.selected_channels()}  # un tubo vacío = 0
        self._push_conteos()
        self.hilo = HiloProceso(str(self.video_path), copy.deepcopy(self.channels), perfil, self,
                                dispositivo="cpu" if self.cb_disp.currentIndex() == 1 else "auto")
        self.hilo.avance.connect(self._on_avance)
        self.hilo.terminado.connect(self._on_terminado)
        self.hilo.fallo.connect(self._on_fallo)
        self.hilo.cancelado.connect(self._on_cancelado)
        self._set_procesando(True)
        self.progreso.setRange(0, 0)  # animación mientras carga el modelo
        self.statusBar().showMessage(f"Cargando el modelo ({descripcion_modelo(perfil)})…")
        self.hilo.start()
        return True

    def _confirmar_lineas(self) -> bool:
        """Antes de procesar: avisa si alguna línea A/B está donde el conteo pierde peces y ofrece corregirla."""
        malas = [c for c in self.selected_channels() if lineas.fuera_de_rango(c.linea_a, c.linea_b)]
        if not malas or not lineas.EDITABLES:
            return True
        detalle = "\n".join(f"  • {c.nombre or c.id}: A {c.linea_a:.0%} / B {c.linea_b:.0%}" for c in malas)
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Warning)
        caja.setWindowTitle("Líneas A/B fuera de rango")
        caja.setText(f"Estas líneas pueden hacer que el conteo pierda peces:\n{detalle}")
        caja.setInformativeText(
            "El pez cuenta si se ve sobre A y después llega a B. Con A muy arriba, los peces que se detectan "
            "hacia la mitad del video no cuentan; con B muy abajo, los que terminan antes tampoco.\n"
            f"Recomendadas: A {lineas.LINEA_A:.0%} / B {lineas.LINEA_B:.0%}.")
        b_reset = caja.addButton("Restablecer y procesar", QMessageBox.AcceptRole)
        b_asi = caja.addButton("Procesar así", QMessageBox.ActionRole)
        caja.addButton("Cancelar", QMessageBox.RejectRole)
        caja.exec()
        if caja.clickedButton() is b_reset:
            for c in malas:
                c.linea_a, c.linea_b = lineas.LINEA_A, lineas.LINEA_B
            self._load_cfg()
            self.canvas.update()
            return True
        return caja.clickedButton() is b_asi

    def _set_procesando(self, activo: bool) -> None:
        for w in (self.left_widget, self.paso1, self.paso2, self.paso4):  # nada de editar mientras corre
            w.setEnabled(not activo)
        self.cb_disp.setEnabled(not activo)
        self.btn_ver.setEnabled(not activo)
        self.progreso.setVisible(activo)
        self.btn_proc.setEnabled(True)
        self.btn_proc.setText("✖  Cancelar" if activo else "⚙  Procesar video")
        tema.poner(self.btn_proc, "cancelar", activo)
        self._actualizar_guia()

    def _fin_proceso(self) -> None:
        if self.hilo is not None:
            self.hilo.wait()
            self.hilo.deleteLater()
            self.hilo = None
        self._set_procesando(False)

    def _on_avance(self, av) -> None:
        if av.total and self.progreso.maximum() == 0:
            self.progreso.setRange(0, av.total)
        if av.total:
            self.progreso.setValue(min(av.cuadro + 1, av.total))
        self.canvas.set_frame(self._a_qimage(av.imagen))
        self.canvas.set_overlay(av.detecciones, av.trayectorias)
        self.conteos = dict(av.conteos)
        self._push_conteos()
        total = av.total or "?"
        self.frame_label.setText(f"Cuadro: {av.cuadro + 1}/{total}")
        self.lbl_resumen.setText(f"Contando… {sum(self.conteos.values())} peces hasta ahora")
        self.statusBar().showMessage(
            f"Procesando… cuadro {av.cuadro + 1}/{total} · {sum(self.conteos.values())} peces contados")

    def _on_terminado(self, res) -> None:
        self._fin_proceso()
        self.resultado, self._exportado = res, False
        self.conteos = {k: int(v) for k, v in res.conteos.items()}
        self._push_conteos()
        self.btn_exportar.setEnabled(True)
        self.lbl_resumen.setText(f"Total: {sum(self.conteos.values())} peces contados en {len(self.conteos)} tubo(s)")
        self.statusBar().showMessage(
            f"Listo: {sum(self.conteos.values())} peces contados en {len(self.conteos)} tubo(s). "
            "Puedes ver o exportar los resultados.")
        self._actualizar_guia()

    def _on_fallo(self, mensaje: str) -> None:
        self._fin_proceso()
        self.conteos = {}
        self._push_conteos()
        self.lbl_resumen.setText("Aún no hay resultados.")
        self.statusBar().showMessage("No se pudo procesar el video.")
        if GPU_NO_SOPORTADA in mensaje:
            self.cb_disp.setCurrentIndex(1)  # deja listo el reintento en CPU
        QMessageBox.critical(self, "No se pudo procesar", mensaje)

    def _on_cancelado(self) -> None:
        self._fin_proceso()
        self.conteos = {}
        self._push_conteos()
        self.canvas.clear_overlay()
        self.lbl_resumen.setText("Aún no hay resultados.")
        self.statusBar().showMessage("Procesamiento cancelado.")

    def ver_resultado(self) -> None:
        if self.resultado is None:  # nada procesado todavía: abrir una carpeta guardada
            self.abrir_resultados()
            return
        self.res_win = ResultadosWindow(self.resultado, "último procesamiento", self)
        self.res_win.show()

    # ---- exportar (T17) ----
    def exportar(self) -> None:
        if self.resultado is None:
            QMessageBox.warning(self, "Sin resultados", "Procesa un video antes de exportar.")
            return
        meta = self.resultado.meta
        sugerido = f"{nombre_secuencia(meta.get('video', ''))}_{meta.get('perfil', 'resultados')}.json"
        inicio = str(self.video_path.parent / sugerido) if self.video_path else sugerido
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar resultados (un solo archivo)", inicio, "JSON (*.json)")
        if ruta:
            self.exportar_en(ruta if ruta.lower().endswith(".json") else ruta + ".json")

    def exportar_en(self, ruta: str) -> bool:
        """Escribe UN archivo JSON con todo (exportar_json.construir_documento) y lo relee para validarlo."""
        res = self.resultado
        try:
            try:
                from tracker.pipeline import cargar_perfil

                perfil = cargar_perfil(res.meta.get("perfil"))
            except Exception:  # sin el YAML del perfil el JSON se escribe igual, sin esa sección
                perfil = None
            guardar_json(ruta, construir_documento(res, perfil))
            leer_json(ruta)  # si no se puede volver a leer, no sirve: mejor enterarse ahora
        except OSError as e:
            QMessageBox.critical(self, "No se pudo escribir el archivo",
                                 f"{e}\n\nElige otra carpeta donde tengas permiso de escritura.")
            return False
        except Exception as e:
            QMessageBox.critical(self, "No se pudo exportar", f"{type(e).__name__}: {e}")
            return False
        self._exportado = True
        self._actualizar_guia()
        self.statusBar().showMessage(f"Exportado: {ruta}")
        QMessageBox.information(self, "Exportado", f"Resultados exportados en un solo archivo ✔\n\n{ruta}")
        return True

    def closeEvent(self, event) -> None:
        if self.hilo is not None:  # no dejar el hilo corriendo al cerrar
            self.hilo.cancelar()
            self.hilo.wait(8000)
        super().closeEvent(event)

    # ---- resultados (conteo por canal y diagnóstico del seguimiento) ----
    def abrir_resultados(self) -> None:
        inicio = str(self.video_path.parent) if self.video_path else ""
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir resultados (JSON exportado)", inicio, "Resultados (*.json)")
        if ruta:
            self.mostrar_resultados_json(ruta)

    def mostrar_resultados_json(self, ruta: str) -> bool:
        try:
            res = leer_json(ruta)
        except (ValueError, OSError) as e:
            QMessageBox.critical(self, "Resultados inválidos", f"No se pudo leer el archivo:\n{ruta}\n\n{e}")
            return False
        self.res_win = ResultadosWindow(res, ruta, self)
        self.res_win.show()
        return True

    def abrir_ejemplo(self) -> None:
        if not EJEMPLO.is_dir():
            QMessageBox.warning(self, "Sin ejemplo", f"No existe la carpeta de ejemplo:\n{EJEMPLO}")
            return
        self.mostrar_resultados(str(EJEMPLO))

    def mostrar_resultados(self, carpeta: str) -> bool:
        from tracker.formato import leer  # lee y valida la carpeta del formato común

        try:
            res = leer(carpeta)
        except (ValueError, OSError, KeyError, TypeError) as e:
            QMessageBox.critical(self, "Resultados inválidos", f"No se pudo leer la carpeta:\n{carpeta}\n\n{e}")
            return False
        self.res_win = ResultadosWindow(res, carpeta, self)
        self.res_win.show()
        return True


def ejecutar() -> int:
    """Punto de entrada de `uv run tracker` (lo llama tracker.cli)."""
    app = QApplication.instance() or QApplication(sys.argv)
    ventana = MainWindow()
    ventana.show()
    return app.exec()


def main() -> None:
    sys.exit(ejecutar())


if __name__ == "__main__":
    main()