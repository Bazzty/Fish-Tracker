"""Conteo por canal.  RESPONSABLE: Alonso (semana 1: línea simple; semana 2: histéresis).

Contrato (lo llama pipeline.procesar una vez por cuadro, después del seguimiento):

    contador = crear_contador(cfg, perfil, canales, fps)
    eventos = contador.actualizar(cuadro, trayectorias)
    contador.conteos()      # {canal_id: n} con TODOS los canales activos; un tubo sin peces da 0

- 'trayectorias': filas de Seguidor.actualizar para ese cuadro.
- Devuelve los eventos de conteo nuevos de ese cuadro:
      {canal, id, cuadro, tiempo_s, conteo}      # 'conteo' = acumulado del canal tras este evento
  con tiempo_s = cuadro / fps. Un mismo (canal, id) cuenta una sola vez.
- Debe ser CAUSAL: decidir solo con lo visto hasta el cuadro actual (la regla del Lab 15 miraba
  la posición final del ID y no servía en vivo).
- perfil['conteo']['tipo']: 'linea_simple' (cruce de linea_a, base) o 'histeresis' (A -> B, variante).

Línea simple (docs/formato_comun.md, regla de conteo): un pez cuenta en el primer cuadro en que su
centro llega a la línea A desde arriba, es decir, en el cuadro anterior en que se vio estaba sobre A
(cy < y_A) y en este está en A o bajo ella (cy >= y_A). Subir no suma ni resta, y un pez que aparece
por primera vez ya bajo la línea no cuenta.

Histéresis (variante): un pez queda «armado» al verse sobre la línea A y cuenta recién al llegar a la
línea B (cy >= y_B), así una caja que oscila sobre una sola línea no suma de más. Además:
- Filtro de trayectorias cortas: no cuenta hasta haberse visto al menos `min_cuadros` cuadros.
- Herencia de estado: un ID nuevo que aparece donde debería estar otro perdido hace poco hereda su estado
  (cuadros vistos, armado, ya contado). «Donde debería estar» = su última posición más su velocidad por los
  cuadros que estuvo perdido; se acepta a menos de `herencia_distancia` veces el alto de su caja, en el mismo
  canal, hasta `herencia_cuadros` cuadros y sin subir. Así un pez que el tracker fragmenta no cuenta dos veces,
  ni pierde el armado aunque reaparezca mucho más abajo (a 10 fps baja hasta ~100 px por cuadro).
Parámetros en perfil['conteo'] (configs/perfiles/variante.yaml).
"""
from typing import Protocol

from tracker.canales import Canal, canal_de


class Contador(Protocol):
    def actualizar(self, cuadro: int, trayectorias: list[dict]) -> list[dict]: ...
    def conteos(self) -> dict[str, int]: ...


class ContadorLinea:
    def __init__(self, canales: list, fps: float):
        self.canales = {c.id: c for c in canales}
        self.fps = fps
        self.previo = {}          # (canal, id) -> cy del último cuadro en que se vio
        self.contados = set()
        self.n = {c.id: 0 for c in canales}

    def actualizar(self, cuadro: int, trayectorias: list[dict]) -> list[dict]:
        eventos = []
        for t in trayectorias:
            canal = self.canales.get(t["canal"])
            if canal is None:
                continue
            clave = (t["canal"], t["id"])
            antes, self.previo[clave] = self.previo.get(clave), t["cy"]
            if clave in self.contados or antes is None:
                continue
            if antes < canal.y_linea(canal.linea_a) <= t["cy"]:
                self.contados.add(clave)
                self.n[canal.id] += 1
                eventos.append(dict(canal=canal.id, id=t["id"], cuadro=cuadro,
                                    tiempo_s=round(cuadro / self.fps, 4), conteo=self.n[canal.id]))
        return eventos

    def conteos(self) -> dict[str, int]:
        return dict(self.n)


class ContadorHisteresis:
    def __init__(self, canales: list, fps: float, min_cuadros: int = 5, herencia_cuadros: int = 15,
                 herencia_distancia: float = 1.5):
        self.canales = {c.id: c for c in canales}
        self.fps = fps
        self.min_cuadros, self.herencia_cuadros, self.herencia_distancia = min_cuadros, herencia_cuadros, herencia_distancia
        self.estado = {}          # (canal, id) -> {visto, armado, contado, cuadro, cx, cy, vx, vy, h, heredado}
        self.n = {c.id: 0 for c in canales}

    def _predecesor(self, canal: str, cuadro: int, t: dict, presentes: set):
        """ID perdido hace poco en el mismo canal, cerca de donde debería estar y sin que el pez haya subido."""
        mejor, dist_min = None, None
        for clave, e in self.estado.items():
            if clave[0] != canal or clave in presentes or e["heredado"]:
                continue
            hueco = cuadro - e["cuadro"]
            if not 0 < hueco <= self.herencia_cuadros:
                continue
            px, py = e["cx"] + e["vx"] * hueco, e["cy"] + e["vy"] * hueco  # posición prevista
            d = ((t["cx"] - px) ** 2 + (t["cy"] - py) ** 2) ** 0.5
            if d <= self.herencia_distancia * e["h"] and t["cy"] >= e["cy"] - e["h"] / 2:
                if dist_min is None or d < dist_min:
                    mejor, dist_min = clave, d
        return mejor

    def actualizar(self, cuadro: int, trayectorias: list[dict]) -> list[dict]:
        eventos = []
        presentes = {(t["canal"], t["id"]) for t in trayectorias}
        for t in trayectorias:
            canal = self.canales.get(t["canal"])
            if canal is None:
                continue
            clave = (t["canal"], t["id"])
            e = self.estado.get(clave)
            if e is None:  # ID nuevo: hereda del que continúa, si lo hay
                e = dict(visto=0, armado=False, contado=False, heredado=False, vx=0.0, vy=0.0)
                previo = self._predecesor(canal.id, cuadro, t, presentes)
                if previo:
                    p = self.estado[previo]
                    p["heredado"] = True
                    e.update(visto=p["visto"], armado=p["armado"], contado=p["contado"], vx=p["vx"], vy=p["vy"])
                self.estado[clave] = e
            elif cuadro > e["cuadro"]:  # velocidad entre las dos últimas apariciones
                dt = cuadro - e["cuadro"]
                e.update(vx=(t["cx"] - e["cx"]) / dt, vy=(t["cy"] - e["cy"]) / dt)
            e.update(visto=e["visto"] + 1, cuadro=cuadro, cx=t["cx"], cy=t["cy"], h=max(t["y2"] - t["y1"], 1.0))
            if t["cy"] < canal.y_linea(canal.linea_a):
                e["armado"] = True
            if (e["armado"] and not e["contado"] and t["cy"] >= canal.y_linea(canal.linea_b)
                    and e["visto"] >= self.min_cuadros):
                e["contado"] = True
                self.n[canal.id] += 1
                eventos.append(dict(canal=canal.id, id=t["id"], cuadro=cuadro,
                                    tiempo_s=round(cuadro / self.fps, 4), conteo=self.n[canal.id]))
        return eventos

    def conteos(self) -> dict[str, int]:
        return dict(self.n)


def crear_contador(cfg: dict, perfil: dict, canales: list, fps: float) -> Contador:
    c = perfil.get("conteo", {})
    tipo = c.get("tipo", "linea_simple")
    activos = [x for x in canales if x.activo]
    if tipo == "linea_simple":
        return ContadorLinea(activos, fps)
    if tipo == "histeresis":
        return ContadorHisteresis(activos, fps, int(c.get("min_cuadros", 5)), int(c.get("herencia_cuadros", 15)),
                                  float(c.get("herencia_distancia", 1.5)))
    raise ValueError(f"Tipo de conteo desconocido: '{tipo}' (use linea_simple o histeresis).")


def canal_cuadro(cfg: dict, ancho: int, alto: int) -> Canal:
    """Un tubo del tamaño del cuadro con la línea A en conteo.linea de config.yaml (referencia por secuencia)."""
    linea = float(cfg["conteo"]["linea"])
    return Canal("canal_1", (0, 0, ancho, alto), "cuadro completo", linea, min(linea + 0.1, 1.0))


def contar_trayectorias(tray: dict, cuadros: list[int], canales: list[Canal], fps: float,
                        conteo: dict | None = None) -> dict[str, int]:
    """Aplica una regla de conteo a trayectorias en formato MOT ({cuadro: [[id, x, y, w, h], ...]}).

    conteo = perfil['conteo'] (por defecto la línea simple). Cada caja va al canal que contiene su centro.
    Lo usan la referencia (trayectorias de DAT-02, siempre con la línea simple) y evaluar_seguimiento
    (trayectorias de cada tracker, con la regla del perfil), así todo cuenta con el mismo código.
    """
    activos = [c for c in canales if c.activo]
    contador = crear_contador({}, {"conteo": conteo or {"tipo": "linea_simple"}}, activos, fps)
    for f in cuadros:
        filas = []
        for i, x, y, w, h in tray.get(f, ()):
            c = canal_de(activos, x + w / 2, y + h / 2)
            if c:
                filas.append(dict(canal=c.id, id=int(i), cx=x + w / 2, cy=y + h / 2, y1=y, y2=y + h))
        contador.actualizar(f, filas)
    return contador.conteos()
