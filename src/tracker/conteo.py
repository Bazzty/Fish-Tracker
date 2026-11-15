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
"""
from typing import Protocol


class Contador(Protocol):
    def actualizar(self, cuadro: int, trayectorias: list[dict]) -> list[dict]: ...
    def conteos(self) -> dict[str, int]: ...


def crear_contador(cfg: dict, perfil: dict, canales: list, fps: float) -> Contador:
    raise NotImplementedError("Pendiente (Alonso): línea simple e histéresis. Ver el contrato en este archivo.")
