"""Formato común con el Validador: exportar, leer y validar una carpeta de resultados.

Especificación completa en docs/formato_comun.md. Una carpeta contiene:
    meta.json, canales.json, detecciones.csv, trayectorias.csv, conteos.csv
"""
import csv
import json
from pathlib import Path

from tracker.canales import cargar_canales, guardar_canales
from tracker.pipeline import Resultados

VERSION = 1
COLUMNAS = {
    "detecciones.csv": ["cuadro", "tiempo_s", "canal", "x1", "y1", "x2", "y2", "conf"],
    "trayectorias.csv": ["cuadro", "tiempo_s", "canal", "id", "x1", "y1", "x2", "y2", "conf", "cx", "cy"],
    "conteos.csv": ["canal", "id", "cuadro", "tiempo_s", "conteo"],
}


def _escribir(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({k: (round(v, 4 if k in ("tiempo_s", "conf") else 2) if isinstance(v, float) else v)
                        for k, v in fila.items()})


def exportar(res: Resultados, carpeta: str | Path) -> Path:
    """Escribe los 5 archivos. Un canal sin peces queda con conteo 0 en meta.json."""
    carpeta = Path(carpeta)
    if not any(c.activo for c in res.canales):
        raise ValueError("No hay canales marcados: no hay nada que exportar.")
    carpeta.mkdir(parents=True, exist_ok=True)
    guardar_canales(carpeta / "canales.json", res.canales, res.meta.get("video"),
                    res.meta.get("ancho"), res.meta.get("alto"))
    _escribir(carpeta / "detecciones.csv", COLUMNAS["detecciones.csv"], res.detecciones)
    _escribir(carpeta / "trayectorias.csv", COLUMNAS["trayectorias.csv"], res.trayectorias)
    _escribir(carpeta / "conteos.csv", COLUMNAS["conteos.csv"], res.eventos)
    conteos = {c.id: int(res.conteos.get(c.id, 0)) for c in res.canales if c.activo}
    meta = {"version": VERSION, **res.meta, "conteos": conteos, "total": sum(conteos.values())}
    (carpeta / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return carpeta


def _leer_csv(ruta: Path) -> list[dict]:
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def leer(carpeta: str | Path) -> Resultados:
    """Lee una carpeta en el formato común (valida antes; lanza ValueError si está mal)."""
    carpeta = Path(carpeta)
    errores = validar(carpeta)
    if errores:
        raise ValueError("Carpeta inválida:\n  " + "\n  ".join(errores))
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    num = lambda f: {k: (float(v) if k in ("tiempo_s", "conf", "x1", "y1", "x2", "y2", "cx", "cy") else
                         int(v) if k in ("cuadro", "id", "conteo") else v) for k, v in f.items()}
    return Resultados(meta=meta, canales=cargar_canales(carpeta / "canales.json"),
                      detecciones=[num(f) for f in _leer_csv(carpeta / "detecciones.csv")],
                      trayectorias=[num(f) for f in _leer_csv(carpeta / "trayectorias.csv")],
                      eventos=[num(f) for f in _leer_csv(carpeta / "conteos.csv")],
                      conteos=meta["conteos"])


def validar(carpeta: str | Path) -> list[str]:
    """Lista de problemas encontrados (vacía si la carpeta cumple el formato)."""
    carpeta, errores = Path(carpeta), []
    for nombre in ["meta.json", "canales.json", *COLUMNAS]:
        if not (carpeta / nombre).is_file():
            errores.append(f"falta {nombre}")
    if errores:
        return errores
    try:
        meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
        ids = {c.id for c in cargar_canales(carpeta / "canales.json")}
    except (ValueError, KeyError, TypeError) as e:
        return [f"meta.json o canales.json ilegible: {e}"]
    if meta.get("version") != VERSION:
        errores.append(f"meta.json: version {meta.get('version')} (se esperaba {VERSION})")
    if not meta.get("conteos") or not set(meta["conteos"]) <= ids:
        errores.append("meta.json: 'conteos' debe traer una entrada por canal activo (0 si no hubo peces)")
    cuentas = {}
    for nombre, columnas in COLUMNAS.items():
        with open(carpeta / nombre, newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f)
            if lector.fieldnames != columnas:
                errores.append(f"{nombre}: columnas {lector.fieldnames}, se esperaba {columnas}")
                continue
            for i, fila in enumerate(lector, start=2):
                try:
                    int(fila["cuadro"]), float(fila["tiempo_s"])
                except ValueError:
                    errores.append(f"{nombre} línea {i}: 'cuadro' o 'tiempo_s' no numérico")
                    break
                if fila["canal"] and fila["canal"] not in ids:
                    errores.append(f"{nombre} línea {i}: canal '{fila['canal']}' no existe en canales.json")
                    break
                if nombre == "conteos.csv":
                    cuentas[fila["canal"]] = cuentas.get(fila["canal"], 0) + 1
    for canal, n in meta.get("conteos", {}).items():
        if cuentas.get(canal, 0) != n:
            errores.append(f"canal {canal}: meta.json dice {n} pero conteos.csv tiene {cuentas.get(canal, 0)} eventos")
    return errores
