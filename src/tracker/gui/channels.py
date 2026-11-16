"""Modelo de canales (tubos) y guardado/carga en JSON.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FORMAT_VERSION = 1


@dataclass
class Channel:
    id: int
    name: str
    points: list[tuple[float, float]]  # polígono del tubo, en px del video
    selected: bool = True  # True = se analiza este canal
    kind: str = "polygon"  # "rect" (4 puntos, editable por bordes) o "polygon"


def save_channels(
    path: str | Path,
    video_path: str | Path,
    frame_size: tuple[int, int],
    channels: list[Channel],
) -> None:
    data = {
        "version": FORMAT_VERSION,
        "video": Path(video_path).name,
        "frame_size": [int(frame_size[0]), int(frame_size[1])],  # [ancho, alto]
        "channels": [
            {
                "id": c.id,
                "name": c.name,
                "selected": c.selected,
                "kind": c.kind,
                "points": [[round(x, 1), round(y, 1)] for x, y in c.points],
            }
            for c in channels
        ],
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_channels(path: str | Path) -> tuple[tuple[int, int], list[Channel]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        w, h = data["frame_size"]
        channels = []
        for c in data["channels"]:
            pts = [(float(x), float(y)) for x, y in c["points"]]
            if len(pts) < 3:
                raise ValueError(f"El canal '{c['name']}' tiene menos de 3 puntos.")
            kind = str(c.get("kind", "polygon"))
            if kind == "rect" and len(pts) != 4:
                kind = "polygon"
            channels.append(Channel(int(c["id"]), str(c["name"]), pts, bool(c.get("selected", True)), kind))
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"Archivo de canales inválido: {e}") from e
    return (int(w), int(h)), channels
