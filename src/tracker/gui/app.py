"""Aplicación de escritorio (PySide6).  RESPONSABLE: Angelo.

Hoy es solo una ventana vacía para que `uv run tracker` abra algo. Por hacer:
  semana 1: abrir video y recorrerlo cuadro a cuadro, dibujar tubos (tracker.canales.Canal),
            marcar la zona de conteo (linea_a / linea_b), seleccionar canales, guardar/cargar JSON
            (canales.guardar_canales / cargar_canales), pantalla de resultados con datos de ejemplo
            (docs/ejemplo_formato/, leer con tracker.formato.leer).
  semana 2: avance en vivo (consumir pipeline.procesar_iter en un hilo aparte: QThread), conteo por
            canal, botón exportar (formato.exportar), mensajes claros ante video inválido o sin tubos.
Dividir en archivos de este paquete (visor.py, editor_canales.py, resultados.py) cuando crezca.
"""
import sys


def ejecutar() -> int:
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    ventana = QMainWindow()
    ventana.setWindowTitle("Tracker - Contador de salmones")
    ventana.setCentralWidget(QLabel("Tracker: interfaz pendiente (src/tracker/gui/app.py)"))
    ventana.resize(640, 360)
    ventana.show()
    return app.exec()
