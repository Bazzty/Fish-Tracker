"""Aplicación de escritorio (PySide6).  RESPONSABLE: Angelo.

Misión 1: abrir un video y recorrerlo (reproducir / cuadro a cuadro), dibujar tubos (canales),
ajustar su zona de conteo (líneas A y B), elegir cuáles se analizan y guardar/cargar el JSON
del formato común (tracker.canales.guardar_canales / cargar_canales).

Punto de entrada para `uv run tracker`: ejecutar().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from tracker.canales import Canal, cargar_canales, guardar_canales

from .canvas import VideoCanvas, color_for, num_de


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tracker - Contador de salmones")
        self.resize(1200, 700)

        self.cap: cv2.VideoCapture | None = None
        self.video_path: Path | None = None
        self.frame_size: tuple[int, int] = (0, 0)
        self.channels: list[Canal] = []
        self._updating_list = False
        self.current = 0
        self.fps = 25.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self.canvas = VideoCanvas()
        self.canvas.channel_drawn.connect(self._on_channel_drawn)
        self.canvas.channel_clicked.connect(self._on_canvas_click)
        self.canvas.editing_changed.connect(self._on_editing_changed)
        self.canvas.channel_edited.connect(lambda _id: self.statusBar().showMessage("Tubo modificado."))
        self.canvas.message.connect(lambda m: self.statusBar().showMessage(m))
        self.canvas.drawing_changed.connect(self._on_drawing_changed)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self._show_frame)
        self.frame_label = QLabel("Cuadro: -")

        left = QVBoxLayout()
        left.addWidget(self.canvas, 1)

        self.btn_prev = QPushButton("◀ Cuadro")
        self.btn_prev.setToolTip("Cuadro anterior (←)")
        self.btn_prev.clicked.connect(lambda: self.step(-1))
        self.btn_play = QPushButton("▶ Reproducir")
        self.btn_play.setToolTip("Reproducir / pausar (Espacio)")
        self.btn_play.setMinimumWidth(110)
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next = QPushButton("Cuadro ▶")
        self.btn_next.setToolTip("Cuadro siguiente (→)")
        self.btn_next.clicked.connect(lambda: self.step(1))
        for b in (self.btn_prev, self.btn_play, self.btn_next):
            b.setFocusPolicy(Qt.NoFocus)
            b.setEnabled(False)

        row = QHBoxLayout()
        row.addWidget(self.btn_prev)
        row.addWidget(self.btn_play)
        row.addWidget(self.btn_next)
        row.addWidget(self.slider, 1)
        row.addWidget(self.frame_label)
        left.addLayout(row)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.toggle_play)
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=lambda: self.step(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=lambda: self.step(1))
        QShortcut(QKeySequence(Qt.Key_Delete), self, activated=self.delete_channel)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self.on_enter)
        QShortcut(QKeySequence(Qt.Key_Enter), self, activated=self.on_enter)

        self.btn_open = QPushButton("Abrir video…")
        self.btn_open.clicked.connect(self.open_video)
        self.btn_draw = QPushButton("Dibujar tubo (arrastrar)")
        self.btn_draw.setToolTip("Arrastra el mouse sobre el video")
        self.btn_draw.clicked.connect(self.start_drawing)
        self.btn_edit = QPushButton("✎ Editar tubo (doble clic)")
        self.btn_edit.clicked.connect(self.toggle_edit)
        self.btn_edit.setEnabled(False)
        self.btn_rename = QPushButton("Renombrar")
        self.btn_rename.clicked.connect(self.rename_channel)
        self.btn_delete = QPushButton("Eliminar tubo (Supr)")
        self.btn_delete.clicked.connect(self.delete_channel)
        self.btn_save = QPushButton("Guardar canales…")
        self.btn_save.clicked.connect(self.save)
        self.btn_load = QPushButton("Cargar canales…")
        self.btn_load.clicked.connect(self.load)

        self.list = QListWidget()
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.installEventFilter(self)  # la lista conserva Espacio y flechas

        hint = QLabel("Líneas A y B: zona de conteo (los peces avanzan de arriba hacia abajo). "
                      "En modo edición, arrastra los círculos amarillos para moverlas.")
        hint.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self.btn_open)
        right.addWidget(QLabel("Tubos (✔ = se analiza). Clic en uno para elegirlo:"))
        right.addWidget(self.list, 1)
        right.addWidget(hint)
        right.addWidget(self.btn_draw)
        right.addWidget(self.btn_edit)
        right.addWidget(self.btn_rename)
        right.addWidget(self.btn_delete)
        right.addWidget(self.btn_save)
        right.addWidget(self.btn_load)
        side = QWidget()
        side.setLayout(right)
        side.setFixedWidth(260)

        root = QHBoxLayout()
        root.addLayout(left, 1)
        root.addWidget(side)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
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
        if not self._confirm_discard("Abrir el video de todos modos"):
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
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.canvas.set_editing(None)
        self.channels = []
        self._refresh_list()
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(n - 1, 0))
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.slider.setEnabled(n > 1)
        for b in (self.btn_prev, self.btn_play, self.btn_next):
            b.setEnabled(n > 1)
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

    def _display(self, frame, idx: int, total: int) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        self.canvas.set_frame(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy())
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

    def step(self, delta: int) -> None:
        """Avanza o retrocede cuadro por cuadro (pausa la reproducción)."""
        if self.cap is None:
            return
        self.pause()
        self.slider.setValue(max(0, min(self.slider.maximum(), self.current + delta)))

    def start_drawing(self) -> None:
        self.pause()
        self.canvas.start_drawing()

    # ---- canales ----
    def _on_drawing_changed(self, drawing: bool) -> None:
        self.btn_draw.setEnabled(not drawing)
        self._update_edit_button()

    def _on_channel_drawn(self, caja: tuple) -> None:
        n = max((num_de(c.id) for c in self.channels), default=0) + 1
        self.channels.append(Canal(f"canal_{n}", caja, f"Tubo {n}"))
        self._refresh_list(keep_row=len(self.channels) - 1)
        self.canvas.set_editing(f"canal_{n}")  # el tubo nuevo queda editable
        self.statusBar().showMessage(
            f"Tubo {n} creado. Ajústalo con los cuadritos blancos, mueve las líneas A y B con los círculos "
            "amarillos. Cuando esté listo, presiona Enter o haz clic fuera para fijarlo."
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
            item = QListWidgetItem(c.nombre or c.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if c.activo else Qt.Unchecked)
            item.setForeground(color_for(c.id))
            self.list.addItem(item)
        self._updating_list = False
        if self.channels and keep_row >= 0:
            self.list.setCurrentRow(min(keep_row, len(self.channels) - 1))
        self.canvas.set_channels(self.channels)
        self._sync_active()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating_list:
            return
        row = self.list.row(item)
        self.list.setCurrentRow(row)
        self.channels[row].activo = item.checkState() == Qt.Checked
        self.canvas.set_channels(self.channels)

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
        self._update_edit_button()

    def _update_edit_button(self) -> None:
        ch = self._current_channel()
        self.btn_edit.setEnabled(ch is not None and not self.canvas.is_drawing)
        if ch is not None and self.canvas.editing_id == ch.id:
            self.btn_edit.setText("✔ Fijar tubo (Enter)")
        else:
            self.btn_edit.setText("✎ Editar tubo (doble clic)")

    def toggle_edit(self) -> None:
        ch = self._current_channel()
        if ch is not None:
            self.canvas.set_editing(None if self.canvas.editing_id == ch.id else ch.id)

    def on_enter(self) -> None:
        if not self.canvas.is_drawing and self.canvas.editing_id is not None:
            self.canvas.set_editing(None)

    def _on_editing_changed(self, channel_id: str) -> None:
        self._update_edit_button()
        if channel_id == "":
            self.statusBar().showMessage("Tubo fijado. Doble clic sobre él (o «Editar tubo») para modificarlo de nuevo.")
        else:
            self.statusBar().showMessage("Editando: arrastra los cuadritos blancos, las líneas A/B o mueve el tubo. "
                                         "Enter o clic fuera para fijar.")

    def rename_channel(self) -> None:
        ch = self._current_channel()
        if ch is None:
            self.statusBar().showMessage("Selecciona un tubo de la lista.")
            return
        name, ok = QInputDialog.getText(self, "Renombrar tubo", "Nombre:", text=ch.nombre)
        if ok and name.strip():
            ch.nombre = name.strip()
            self._refresh_list(keep_row=self.list.currentRow())

    def delete_channel(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            self.statusBar().showMessage("Haz clic en el nombre de un tubo de la lista para elegirlo y luego Eliminar.")
            return
        name = self.channels[row].nombre
        if QMessageBox.question(self, "Eliminar tubo", f"¿Eliminar '{name}'?") != QMessageBox.Yes:
            return
        del self.channels[row]
        self._refresh_list(keep_row=row)
        self.statusBar().showMessage(f"'{name}' eliminado.")

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
        self.statusBar().showMessage(f"Cargados {len(channels)} tubos (todos fijos).")
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
