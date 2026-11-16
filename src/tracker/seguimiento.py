"""Seguimiento por canal.  RESPONSABLE: Alonso (semana 1: ByteTrack por canal; semana 2: ajuste y otros trackers).

Contrato (lo llama pipeline.procesar una vez por cuadro, en orden):

    seguidor = crear_seguidor(cfg, perfil, canales)
    trayectorias = seguidor.actualizar(cuadro, detecciones)

- 'detecciones': lo que devuelve Detector.detectar (lista de dicts x1, y1, x2, y2, conf).
- Devuelve una fila por pez seguido en ese cuadro, SOLO de canales activos:
      {canal, id, x1, y1, x2, y2, conf, cx, cy}
  'id' es único dentro del canal y no se reutiliza. Un pez cuyo centro cae fuera de todo canal
  activo no genera fila. Debe llamarse también con listas vacías para que los IDs perdidos envejezcan.
- Se puede reutilizar contar.nuevo_tracker (ByteTrack del Lab 15) y comun.* en vez de reescribirlos.
"""
from typing import Protocol


class Seguidor(Protocol):
    def actualizar(self, cuadro: int, detecciones: list[dict]) -> list[dict]: ...


def crear_seguidor(cfg: dict, perfil: dict, canales: list) -> Seguidor:
    raise NotImplementedError("Pendiente (Alonso): ByteTrack por canal. Ver el contrato en este archivo.")
