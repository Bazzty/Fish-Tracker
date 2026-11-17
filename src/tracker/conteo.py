"""Conteo por canal.  RESPONSABLE: Alonso (semana 1: línea simple; semana 2: histéresis).

Contrato (lo llama pipeline.procesar una vez por cuadro, después del seguimiento):

    contador = crear_contador(cfg, perfil, canales, fps)
    eventos = contador.actualizar(cuadro, trayectorias)
    contador.conteos()      # {canal_id: n} con TODOS los canales activos; un tubo sin peces da 0

- 'trayectorias': filas de Seguidor.actualizar para ese cuadro.
- Devuelve los eventos de conteo nuevos de ese cuadro:
      {canal, id, cuadro, tiempo_s, conteo}      # 'conteo' = acumulado del canal tras este evento
  con tiempo_s = cuadro / fps. Un mismo (canal, id) cuenta una sola vez.
- Debe ser CAUSAL: decidir solo con lo visto hasta el cuadro actual (la regla vieja de
  contar.contar_cruces mira la posición final del ID y no sirve en vivo).
- perfil['conteo']['tipo']: 'linea_simple' (cruce de linea_a, base) o 'histeresis' (A -> B, variante).

Línea simple (docs/formato_comun.md, regla de conteo): un pez cuenta en el primer cuadro en que su
centro llega a la línea A desde arriba, es decir, en el cuadro anterior en que se vio estaba sobre A
(cy < y_A) y en este está en A o bajo ella (cy >= y_A). Subir no suma ni resta, y un pez que aparece
por primera vez ya bajo la línea no cuenta.
"""
from typing import Protocol


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


def crear_contador(cfg: dict, perfil: dict, canales: list, fps: float) -> Contador:
    tipo = perfil.get("conteo", {}).get("tipo", "linea_simple")
    activos = [c for c in canales if c.activo]
    if tipo == "linea_simple":
        return ContadorLinea(activos, fps)
    if tipo == "histeresis":
        raise NotImplementedError("Pendiente (Alonso, semana 2): conteo con histéresis A -> B.")
    raise ValueError(f"Tipo de conteo desconocido: '{tipo}' (use linea_simple o histeresis).")
