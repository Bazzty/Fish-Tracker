"""Aplicación de escritorio (PySide6).  RESPONSABLE: Angelo.

Misión 1: abrir un video (reproducir / barra), dibujar tubos (canales), configurarlos (nombre, zona de
conteo A/B, posición y tamaño), elegir cuáles se analizan y guardar/cargar el JSON del formato común
(tracker.canales.guardar_canales / cargar_canales).
Resultados: menú «Resultados» (conteo por canal y diagnóstico del seguimiento).

Punto de entrada para `uv run tracker`: ejecutar().
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import cv2
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from tracker.canales import Canal, cargar_canales, guardar_canales

from . import lineas, proceso
from .canvas import VideoCanvas, color_for, num_de
from .proceso import GPU_NO_SOPORTADA, HiloProceso, descripcion_modelo, nombre_modelo
from .resultados import ResultadosWindow

# Resultados de ejemplo del repo (formato común): <repo>/docs/ejemplo_formato
EJEMPLO = Path(__file__).resolve().parents[3] / "docs" / "ejemplo_formato"
MIN_GAP_PCT = 2  # separación mínima entre las líneas A y B (en %)


def _en_campo_de_texto() -> bool:
    return isinstance(QApplication.focusWidget(), (QLineEdit, QAbstractSpinBox))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tracker - Contador de salmones")
        self.resize(1250, 720)

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
        self.slider.valueChanged.connect(self._show_frame)
        self.frame_label = QLabel("Cuadro: -")
        self.btn_play = QPushButton("▶ Reproducir")
        self.btn_play.setToolTip("Reproducir / pausar (Espacio)")
        self.btn_play.setMinimumWidth(110)
        self.btn_play.setFocusPolicy(Qt.NoFocus)
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_play)

        row = QHBoxLayout()
        row.addWidget(self.btn_play)
        row.addWidget(self.slider, 1)
        row.addWidget(self.frame_label)
        left = QVBoxLayout()
        left.addWidget(self.canvas, 1)
        left.addLayout(row)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._atajo_play)
        QShortcut(QKeySequence(Qt.Key_Delete), self, activated=self._atajo_eliminar)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self.on_enter)
        QShortcut(QKeySequence(Qt.Key_Enter), self, activated=self.on_enter)

        # ---- panel derecho ----
        self.btn_open = QPushButton("Abrir video…")
        self.btn_open.clicked.connect(self.open_video)
        self.list = QListWidget()
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.installEventFilter(self)  # la lista conserva Espacio y flechas

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
        form = QFormLayout()
        form.addRow("Nombre", self.ed_nombre)
        form.addRow(self.chk_activo)
        form.addRow("Línea A (entrada)" + ("" if lineas.EDITABLES else " · fija"), self.sp_a)
        form.addRow("Línea B (salida)" + ("" if lineas.EDITABLES else " · fija"), self.sp_b)
        form.addRow("X", self.sp_x)
        form.addRow("Y", self.sp_y)
        form.addRow("Ancho", self.sp_w)
        form.addRow("Alto", self.sp_h)
        self.cfg = QGroupBox("Configuración del tubo")
        self.cfg.setLayout(form)
        self._cfg_widgets = [self.ed_nombre, self.chk_activo, self.sp_a, self.sp_b,
                             self.sp_x, self.sp_y, self.sp_w, self.sp_h]

        self.btn_draw = QPushButton("Dibujar tubo (arrastrar)")
        self.btn_draw.setToolTip("Arrastra el mouse sobre el video")
        self.btn_draw.clicked.connect(self.start_drawing)
        self.btn_done = QPushButton("✔ Listo (Enter)")
        self.btn_done.setToolTip("Fija el tubo para no moverlo por accidente")
        self.btn_done.clicked.connect(lambda: self.canvas.set_editing(None))
        self.btn_done.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar tubo (Supr)")
        self.btn_delete.clicked.connect(self.delete_channel)
        self.btn_save = QPushButton("Guardar canales…")
        self.btn_save.clicked.connect(self.save)
        self.btn_load = QPushButton("Cargar canales…")
        self.btn_load.clicked.connect(self.load)

        right = QVBoxLayout()
        right.addWidget(self.btn_open)
        right.addWidget(QLabel("Tubos (✔ = se analiza). Clic en un tubo del video para configurarlo:"))
        right.addWidget(self.list, 1)
        right.addWidget(self.cfg)
        right.addWidget(self.btn_draw)
        right.addWidget(self.btn_done)
        right.addWidget(self.btn_delete)
        right.addWidget(self.btn_save)
        right.addWidget(self.btn_load)
        side = QWidget()
        side.setLayout(right)
        side.setFixedWidth(290)

        root = QHBoxLayout()
        root.addLayout(left, 1)
        root.addWidget(side)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)


        barra = self.addToolBar("Procesamiento")
        barra.setMovable(False)
        self.lbl_modelo = QLabel(f" Modelo: {nombre_modelo()} ")
        self.lbl_modelo.setToolTip(f"{descripcion_modelo()}\nPerfil '{proceso.PERFIL}' "
                                   f"(configs/perfiles/{proceso.PERFIL}.yaml)")
        barra.addWidget(self.lbl_modelo)
        barra.addWidget(QLabel("  Dispositivo: "))
        self.cb_disp = QComboBox()
        self.cb_disp.addItems(["Automático (GPU si sirve)", "CPU"])
        self.cb_disp.setToolTip("Si tu GPU es antigua y falla, elige CPU (más lento)")
        barra.addWidget(self.cb_disp)
        self.btn_proc = QPushButton("⚙ Procesar video")
        self.btn_proc.setToolTip("Detecta, sigue y cuenta los peces de los tubos marcados (✔)")
        self.btn_proc.clicked.connect(self.toggle_proceso)
        barra.addWidget(self.btn_proc)
        self.btn_exportar = QPushButton("Exportar resultados…")
        self.btn_exportar.setToolTip("Guarda el formato común (meta, canales, detecciones, trayectorias, conteos)")
        self.btn_exportar.setEnabled(False)
        self.btn_exportar.clicked.connect(self.exportar)
        barra.addWidget(self.btn_exportar)
        self.btn_ver = QPushButton("Ver resultados")
        self.btn_ver.setToolTip("Muestra el último procesamiento; si no hay uno, deja abrir una carpeta de resultados "
                                "(p. ej. docs/ejemplo_formato)")
        self.btn_ver.clicked.connect(self.ver_resultado)
        barra.addWidget(self.btn_ver)
        self.progreso = QProgressBar()
        self.progreso.setMaximumWidth(280)
        self.progreso.setVisible(False)
        self.statusBar().addPermanentWidget(self.progreso)
        self.res_win = None
        self._load_cfg()
        self.statusBar().showMessage("Abre un video para comenzar.")

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
        self.statusBar().showMessage(f"{self.video_path.name}: {w}x{h}, {n} cuadros.")
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
        self.btn_draw.setEnabled(not drawing)

    def _on_channel_drawn(self, caja: tuple) -> None:
        n = max((num_de(c.id) for c in self.channels), default=0) + 1
        self.channels.append(Canal(f"canal_{n}", caja, f"Tubo {n}", linea_a=lineas.LINEA_A, linea_b=lineas.LINEA_B))
        self._refresh_list(keep_row=len(self.channels) - 1)
        self.canvas.set_editing(f"canal_{n}")  # el tubo nuevo queda editable
        self.statusBar().showMessage(
            f"Tubo {n} creado. Ajústalo con los cuadritos blancos o con el panel "
            "(las líneas A y B son fijas). Cuando esté listo, Enter o clic fuera."
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
            item.setForeground(color_for(c.id))
            self.list.addItem(item)
        self._updating_list = False
        if self.channels and keep_row >= 0:
            self.list.setCurrentRow(min(keep_row, len(self.channels) - 1))
        self.canvas.set_channels(self.channels)
        self._sync_active()

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
            self.statusBar().showMessage("Configurando el tubo: arrastra los cuadritos blancos, las líneas A/B, "
                                         "o usa el panel. Enter o clic fuera para fijar.")

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
        for w in self._cfg_widgets:
            w.setEnabled(ch is not None)
        if not lineas.EDITABLES:  # las líneas A y B se ven, pero no se editan
            self.sp_a.setEnabled(False)
            self.sp_b.setEnabled(False)
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
            ch.caja = (float(x), float(y), float(x2), float(y2))
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
            guardar_canales(path, self.channels, self.video_path.name, *self.frame_size)
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
            channels = cargar_canales(path)
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
        distintas = [c for c in channels
                     if abs(c.linea_a - lineas.LINEA_A) > 0.005 or abs(c.linea_b - lineas.LINEA_B) > 0.005]
        aviso = (f" Traen sus propias líneas A/B (p. ej. {distintas[0].linea_a:.0%}/{distintas[0].linea_b:.0%}): "
                 "se respetan tal cual y no se pueden editar." if distintas and not lineas.EDITABLES else "")
        self.statusBar().showMessage(f"Cargados {len(channels)} tubos (todos fijos).{aviso}")
        return True

    # ---- procesamiento en vivo (T15) ----
    def _reset_resultados(self) -> None:
        self.conteos = {}
        self.resultado = None
        self._exportado = False
        self.btn_exportar.setEnabled(False)
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

    def _set_procesando(self, activo: bool) -> None:
        self.centralWidget().setEnabled(not activo)  # nada de editar mientras corre
        self.cb_disp.setEnabled(not activo)
        self.btn_ver.setEnabled(not activo)
        self.progreso.setVisible(activo)
        self.btn_proc.setEnabled(True)
        self.btn_proc.setText("✖ Cancelar" if activo else "⚙ Procesar video")

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
        self.statusBar().showMessage(
            f"Procesando… cuadro {av.cuadro + 1}/{total} · {sum(self.conteos.values())} peces contados")

    def _on_terminado(self, res) -> None:
        self._fin_proceso()
        self.resultado, self._exportado = res, False
        self.conteos = {k: int(v) for k, v in res.conteos.items()}
        self._push_conteos()
        self.btn_exportar.setEnabled(True)
        self.statusBar().showMessage(
            f"Listo: {sum(self.conteos.values())} peces contados en {len(self.conteos)} tubo(s). "
            "Puedes ver o exportar los resultados.")

    def _on_fallo(self, mensaje: str) -> None:
        self._fin_proceso()
        self.conteos = {}
        self._push_conteos()
        self.statusBar().showMessage("No se pudo procesar el video.")
        if GPU_NO_SOPORTADA in mensaje:
            self.cb_disp.setCurrentIndex(1)  # deja listo el reintento en CPU
        QMessageBox.critical(self, "No se pudo procesar", mensaje)

    def _on_cancelado(self) -> None:
        self._fin_proceso()
        self.conteos = {}
        self._push_conteos()
        self.canvas.clear_overlay()
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
        base = QFileDialog.getExistingDirectory(self, "Elegir la carpeta donde guardar los resultados")
        if base:
            self.exportar_en(base)

    def exportar_en(self, base: str) -> bool:
        """Escribe el formato común en <base>/<video>_<perfil>/ y lo valida."""
        from tracker import formato

        res = self.resultado
        nombre = f"{Path(res.meta.get('video', 'video')).stem}_{res.meta.get('perfil', 'perfil')}"
        carpeta = Path(base) / nombre
        if carpeta.is_dir() and any(carpeta.iterdir()):
            r = QMessageBox.question(self, "Carpeta existente",
                                     f"La carpeta ya tiene archivos:\n{carpeta}\n¿Reemplazar los del formato común?")
            if r != QMessageBox.Yes:
                return False
        try:
            formato.exportar(res, carpeta)
        except ValueError as e:
            QMessageBox.critical(self, "No se pudo exportar", str(e))
            return False
        except OSError as e:
            QMessageBox.critical(self, "No se pudo escribir en la carpeta",
                                 f"{e}\n\nElige otra carpeta donde tengas permiso de escritura.")
            return False
        errores = formato.validar(carpeta)
        if errores:
            QMessageBox.warning(self, "Exportado, pero con problemas",
                                "Los archivos se escribieron, pero no cumplen el formato común:\n- " + "\n- ".join(errores))
            return False
        self._exportado = True
        self.statusBar().showMessage(f"Exportado y validado: {carpeta}")
        QMessageBox.information(self, "Exportado",
                                f"Resultados exportados y validados contra el formato común ✔\n\n{carpeta}")
        return True

    def closeEvent(self, event) -> None:
        if self.hilo is not None:  # no dejar el hilo corriendo al cerrar
            self.hilo.cancelar()
            self.hilo.wait(8000)
        super().closeEvent(event)

    # ---- resultados (conteo por canal y diagnóstico del seguimiento) ----
    def abrir_resultados(self) -> None:
        inicio = str(EJEMPLO.parent) if EJEMPLO.parent.is_dir() else ""
        carpeta = QFileDialog.getExistingDirectory(self, "Carpeta de resultados (formato común)", inicio)
        if carpeta:
            self.mostrar_resultados(carpeta)

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