"""Pantalla de resultados: conteo por canal (T10) y diagnóstico del seguimiento (T11)."""
from __future__ import annotations

import csv

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import lineas
from .canvas import color_for
from .diagnostico import ETIQUETAS, TIPOS, diagnosticar


def _llenar(t: QTableWidget, filas: list) -> None:
    t.setRowCount(len(filas))
    for i, fila in enumerate(filas):
        for j, v in enumerate(fila):
            it = QTableWidgetItem(str(v))
            if not isinstance(v, str):
                it.setTextAlignment(Qt.AlignCenter)
            t.setItem(i, j, it)


def _tabla(columnas: list[str], filas: list, estirar: int | None = None) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    h = t.horizontalHeader()
    for j in range(len(columnas)):
        modo = QHeaderView.Stretch if (estirar is None or j == estirar) else QHeaderView.ResizeToContents
        h.setSectionResizeMode(j, modo)
    _llenar(t, filas)
    return t


class BarrasConteo(QWidget):
    """Barras horizontales: un conteo por canal (un tubo vacío se ve con 0)."""

    def __init__(self, datos: list[tuple[str, str, int]]) -> None:  # (id, nombre, conteo)
        super().__init__()
        self.datos = datos
        self.setMinimumHeight(34 * max(1, len(datos)) + 10)

    def paintEvent(self, _) -> None:
        if not self.datos:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        texto = self.palette().text().color()
        mx = max(1, max(n for _i, _n, n in self.datos))
        izq, der = 140, 50
        for i, (cid, nombre, n) in enumerate(self.datos):
            y = 5 + i * 34
            p.setPen(texto)
            p.drawText(0, y, izq - 8, 24, int(Qt.AlignVCenter | Qt.AlignRight), nombre)
            w = max(2.0, (self.width() - izq - der) * n / mx)
            p.setPen(Qt.NoPen)
            p.setBrush(color_for(cid))
            p.drawRoundedRect(izq, y + 2, int(w), 20, 4, 4)
            p.setPen(texto)
            p.drawText(int(izq + w + 6), y, 40, 24, int(Qt.AlignVCenter | Qt.AlignLeft), str(n))


class ResultadosWindow(QDialog):
    def __init__(self, res, carpeta: str, parent=None) -> None:
        super().__init__(parent)
        self.res = res
        self.diag = diagnosticar(res)
        self.setWindowTitle(f"Resultados - {carpeta}")
        self.resize(1050, 680)
        tabs = QTabWidget()
        tabs.addTab(self._tab_conteo(), "Conteo por canal")
        tabs.addTab(self._tab_diagnostico(), "Diagnóstico del seguimiento")
        tabs.addTab(self._tab_trayectorias(), "Trayectorias y línea A")
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)

    # ---- T10: conteo por canal ----
    def _tab_conteo(self) -> QWidget:
        res, m = self.res, self.res.meta
        nombres = {c.id: (c.nombre or c.id) for c in res.canales}
        orden = [c.id for c in res.canales if c.id in res.conteos] + [k for k in res.conteos if k not in nombres]
        filas = [[nombres.get(k, k), k, int(res.conteos[k])] for k in orden]
        total = sum(f[2] for f in filas)

        cab = QLabel(
            f"Video: {m.get('video', '?')}    Perfil: {m.get('perfil', '?')}    "
            f"Cuadros: {m.get('cuadros', '?')}    FPS: {m.get('fps', '?')}"
        )
        cab.setWordWrap(True)
        tabla = _tabla(["Tubo", "Canal", "Conteo"], filas + [["TOTAL", "", total]])
        tabla.setMaximumHeight(34 + 30 * (len(filas) + 1))
        barras = BarrasConteo([(k, n, c) for n, k, c in filas])
        nota = QLabel("Un tubo sin peces cuenta 0.")

        eventos = sorted(res.eventos, key=lambda e: (e["cuadro"], e["canal"]))
        ev = _tabla(
            ["Canal", "ID", "Cuadro", "Tiempo (s)", "Conteo acumulado"],
            [[e["canal"], e["id"], e["cuadro"], e["tiempo_s"], e["conteo"]] for e in eventos],
        )
        izq = QVBoxLayout()
        izq.addWidget(tabla)
        izq.addWidget(barras)
        izq.addWidget(nota)
        izq.addStretch(1)
        der = QVBoxLayout()
        der.addWidget(QLabel(f"Eventos de conteo ({len(eventos)})"))
        der.addWidget(ev)
        fila = QHBoxLayout()
        fila.addLayout(izq, 1)
        fila.addLayout(der, 1)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(cab)
        lay.addLayout(fila, 1)
        return w

    # ---- T11: diagnóstico del seguimiento ----
    def _tab_diagnostico(self) -> QWidget:
        d, w = self.diag, QWidget()
        lay = QVBoxLayout(w)
        if not d.hay_trayectorias:
            lay.addWidget(QLabel("Estos resultados no traen trayectorias (¿corrida solo con el detector?).\n"
                                 "El diagnóstico necesita trayectorias.csv con seguimiento."))
            lay.addStretch(1)
            return w
        p = d.params
        expl = QLabel(
            "<b>Caja intermitente</b>: el ID desaparece unos cuadros y reaparece.  "
            "<b>ID perdido</b>: el ID termina en medio del tubo.  "
            "<b>ID nuevo</b>: un ID aparece en medio del tubo.<br>"
            "Un ID perdido seguido de un ID nuevo cercano es una <b>fragmentación probable</b> "
            "(el mismo pez con dos IDs: riesgo de contarlo dos veces). "
            "Es una heurística sobre las trayectorias, no una verificación contra etiquetas."
        )
        expl.setWordWrap(True)
        lay.addWidget(expl)

        nombres = {c.id: (c.nombre or c.id) for c in self.res.canales}
        filas, tot = [], dict.fromkeys(("ids", *TIPOS, "fragmentaciones"), 0)
        for canal, r in sorted(d.resumen.items()):
            filas.append([nombres.get(canal, canal), r["ids"], *(r[t] for t in TIPOS), r["fragmentaciones"]])
            for k in tot:
                tot[k] += r[k]
        filas.append(["TOTAL", tot["ids"], *(tot[t] for t in TIPOS), tot["fragmentaciones"]])
        lay.addWidget(_tabla(["Canal", "IDs", *(ETIQUETAS[t] for t in TIPOS), "Fragmentaciones probables"], filas))
        lay.itemAt(lay.count() - 1).widget().setMaximumHeight(34 + 30 * len(filas))
        lay.addWidget(QLabel(
            f"Trayectorias de menos de {p.min_cuadros} cuadros ({d.cortas}) no se juzgan como perdidas/nuevas. "
            f"Borde de entrada/salida: {p.borde:.0%} del alto del tubo; ventana de enlace: {p.ventana} cuadros."
        ))

        top = QHBoxLayout()
        top.addWidget(QLabel("Detalle de fallos:"))
        self.filtro = QComboBox()
        self.filtro.addItem("Todos", None)
        for t in TIPOS:
            self.filtro.addItem(ETIQUETAS[t], t)
        self.filtro.currentIndexChanged.connect(self._filtrar)
        top.addWidget(self.filtro)
        top.addStretch(1)
        btn = QPushButton("Exportar diagnóstico (CSV)…")
        btn.clicked.connect(self.exportar)
        top.addWidget(btn)
        lay.addLayout(top)
        self.detalle = _tabla(["Tipo", "Canal", "ID", "Cuadro", "Tiempo (s)", "Detalle"], [], estirar=5)
        lay.addWidget(self.detalle, 1)
        self._filtrar()
        return w

    # ---- ¿por qué no se contó? trayectorias y posición de la línea A ----
    def _tab_trayectorias(self) -> QWidget:
        d, w = self.diag, QWidget()
        lay = QVBoxLayout(w)
        if not d.hay_trayectorias:
            lay.addWidget(QLabel("No hay trayectorias en estos resultados."))
            lay.addStretch(1)
            return w
        nombres = {c.id: (c.nombre or c.id) for c in self.res.canales}
        textos = [
            "<b>Regla del perfil base:</b> un pez se cuenta cuando se ve <b>por encima</b> de la línea A y después "
            "en la línea o más abajo. Si un ID nace ya bajo la línea A, o se pierde antes de llegar, <b>no se cuenta</b>: "
            "el conteo puede salir 0 aunque pasen peces. Los peces deben ir de arriba hacia abajo."
        ]
        for cid, g in d.guias.items():
            if g.n == 0:
                textos.append(f"<b>{nombres.get(cid, cid)}</b>: sin trayectorias.")
                continue
            t = (f"<b>{nombres.get(cid, cid)}</b>: línea A en {g.linea_a:.0%}; "
                 f"{g.cruzan} de {g.n} trayectorias la cruzan.")
            if g.p_ini is not None:
                t += (f" Las trayectorias largas suelen nacer por encima del {g.p_ini:.0%} del alto "
                      f"y terminar por debajo del {g.p_fin:.0%}.")
                t += (f" <b>La línea A funcionaría entre {g.sugerida[0]:.0%} y {g.sugerida[1]:.0%}.</b>" if g.sugerida
                      else " No hay un rango claro: el seguimiento corta las trayectorias antes de que nazcan las siguientes.")
            textos.append(t)
        if not lineas.EDITABLES:
            textos.append(f"<i>Las líneas de los tubos dibujados en la GUI son fijas (A {lineas.LINEA_A:.0%}, "
                          f"B {lineas.LINEA_B:.0%}); se definen en lineas.py.</i>")
        info = QLabel("<br>".join(textos))
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addWidget(_tabla(
            ["Canal", "ID", "Cuadros", "Veces visto", "% alto al inicio", "% alto al final", "Sentido", "¿Cruza la línea A?"],
            [[nombres.get(x.canal, x.canal), x.id, f"{x.ini}–{x.fin}", x.n, f"{x.rel_ini:.0%}", f"{x.rel_fin:.0%}",
              x.sentido, "Sí" if x.cruza_a else "No"] for x in d.pistas]), 1)
        return w

    def _filtrar(self) -> None:
        tipo = self.filtro.currentData()
        _llenar(self.detalle, [
            [ETIQUETAS[f.tipo], f.canal, f.id, f.cuadro, f.tiempo_s, f.detalle]
            for f in self.diag.fallos if tipo is None or f.tipo == tipo
        ])

    def exportar(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar diagnóstico", "diagnostico.csv", "CSV (*.csv)")
        if path:
            self.exportar_a(path)

    def exportar_a(self, path: str) -> bool:
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["tipo", "canal", "id", "cuadro", "tiempo_s", "detalle", "enlace"])
                for x in self.diag.fallos:
                    w.writerow([x.tipo, x.canal, x.id, x.cuadro, x.tiempo_s, x.detalle, x.enlace or ""])
        except OSError as e:
            QMessageBox.critical(self, "Error al exportar", str(e))
            return False
        return True
