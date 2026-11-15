"""Análisis de datos: paso 1 (resumen), paso 2 (tamaños de caja) y paso 3 (saltos entre cuadros).

Uso: uv run python src/analisis.py
Salida: docs/tablas/*.csv y docs/figuras/*.png
"""
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"
TABLAS = RAIZ / "docs" / "tablas"
FIGURAS = RAIZ / "docs" / "figuras"
NUM = re.compile(r"_(\d+)\.")


def cargar_cuadros():
    filas = []
    for s in sorted(DATA.glob("seq_*")):
        for img in sorted((s / "images").glob("*.jp*g")):
            if img.name.startswith("."):
                continue
            ancho, alto = Image.open(img).size
            txt = s / "labels" / (img.stem + ".txt")
            n = len([l for l in txt.read_text().splitlines() if l.strip()]) if txt.exists() else 0
            filas.append(dict(seq=s.name, num=int(NUM.search(img.name).group(1)),
                              ancho=ancho, alto=alto, n_cajas=n))
    return pd.DataFrame(filas).sort_values(["seq", "num"]).reset_index(drop=True)


def resumen(c):
    g = c.groupby("seq")
    r = g.agg(
        cuadros=("num", "size"),
        con_salmon=("n_cajas", lambda s: int((s > 0).sum())),
        sin_salmon=("n_cajas", lambda s: int((s == 0).sum())),
        cajas=("n_cajas", "sum"),
        max_por_cuadro=("n_cajas", "max"),
        resolucion=("ancho", lambda s: ""),
    )
    r["resolucion"] = [f"{a.iloc[0]}x{h.iloc[0]}" for (_, a), (_, h) in zip(g.ancho, g.alto)]
    r["pct_sin_salmon"] = (100 * r.sin_salmon / r.cuadros).round(1)
    r["media_por_cuadro_con_salmon"] = (r.cajas / r.con_salmon).round(2)
    total = r[["cuadros", "con_salmon", "sin_salmon", "cajas"]].sum()
    r.loc["TOTAL", total.index] = total
    cols_int = ["cuadros", "con_salmon", "sin_salmon", "cajas", "max_por_cuadro"]
    r[cols_int] = r[cols_int].fillna(0).astype(int)
    r.loc["TOTAL", ["max_por_cuadro", "resolucion"]] = [r.max_por_cuadro.iloc[:-1].max(), "-"]
    r.loc["TOTAL", "pct_sin_salmon"] = round(100 * total.sin_salmon / total.cuadros, 1)
    r.loc["TOTAL", "media_por_cuadro_con_salmon"] = round(total.cajas / total.con_salmon, 2)
    return r


# --- Paso 2: tamaños de caja ---
def cargar_cajas(c):
    filas = []
    for f in c[c.n_cajas > 0].itertuples():
        txt = DATA / f.seq / "labels" / f"{f.seq}_{f.num:05d}.txt"
        if not txt.exists():  # nombre con otro padding: buscar por número
            txt = next((DATA / f.seq / "labels").glob(f"*_{f.num:0{len(str(f.num))}d}.txt"), None)
        for l in txt.read_text().splitlines():
            if l.strip():
                _, _, _, w, h = map(float, l.split()[:5])
                filas.append(dict(seq=f.seq, w=w * f.ancho, h=h * f.alto, W=f.ancho, H=f.alto))
    b = pd.DataFrame(filas)
    b["area"] = b.w * b.h
    b["pct_imagen"] = 100 * b.area / (b.W * b.H)
    b["aspecto"] = b.w / b.h
    return b


def tamanos(b):
    cols = ["w", "h", "area", "pct_imagen", "aspecto"]
    glob = b[cols].describe(percentiles=[.05, .5, .95]).T.round(2)
    por_seq = b.groupby("seq")[cols].agg(["min", "median", "max"]).round(1)
    return glob, por_seq


def figura_tamanos(b):
    FIGURAS.mkdir(parents=True, exist_ok=True)
    f, axs = plt.subplots(1, 3, figsize=(13, 4))
    for ax, col, t in zip(axs, ["w", "h", "area"], ["Ancho (px)", "Alto (px)", "Área (px²)"]):
        ax.hist(b[col], bins=40)
        ax.set(title=t, ylabel="cajas")
    f.suptitle("Tamaño de las cajas (todas las secuencias)")
    f.tight_layout()
    f.savefig(FIGURAS / "tamanos_hist.png", dpi=150)
    plt.close(f)

    seqs = sorted(b.seq.unique())
    f, axs = plt.subplots(1, 3, figsize=(13, 4))
    for ax, col, t in zip(axs, ["w", "h", "area"], ["Ancho (px)", "Alto (px)", "Área (px²)"]):
        ax.boxplot([b[b.seq == s][col] for s in seqs], tick_labels=[s[-4:] for s in seqs])
        ax.set(title=t, xlabel="secuencia")
    f.suptitle("Tamaño de las cajas por secuencia")
    f.tight_layout()
    f.savefig(FIGURAS / "tamanos_por_secuencia.png", dpi=150)
    plt.close(f)


# --- Paso 3: saltos entre cuadros (solo descripción) ---
def saltos(c):
    s = c.groupby("seq").num.diff().dropna().astype(int)
    c = c.assign(salto=c.groupby("seq").num.diff())
    por_seq = c.groupby("seq").agg(
        cuadros=("num", "size"),
        num_min=("num", "min"),
        num_max=("num", "max"),
        saltos_mayor_1=("salto", lambda x: int((x > 1).sum())),
        salto_mediano=("salto", "median"),
        salto_p90=("salto", lambda x: x.quantile(.9)),
        salto_max=("salto", "max"),
    )
    por_seq["pct_consecutivos"] = (
        100 * c.groupby("seq").salto.apply(lambda x: (x == 1).sum() / x.notna().sum())
    ).round(1)
    por_seq["frames_omitidos"] = por_seq.num_max - por_seq.num_min + 1 - por_seq.cuadros
    por_seq["pct_omitidos"] = (100 * por_seq.frames_omitidos / (por_seq.num_max - por_seq.num_min + 1)).round(1)
    cuant = s.quantile([.5, .75, .9, .95, .99, 1]).rename("salto")
    return por_seq, cuant, s


def figura_saltos(s):
    FIGURAS.mkdir(parents=True, exist_ok=True)
    f, axs = plt.subplots(1, 2, figsize=(12, 4))
    axs[0].hist(s, bins=range(1, 12), align="left")
    axs[0].set(title="Saltos pequeños (1 a 11)", xlabel="salto entre cuadros", ylabel="frecuencia")
    axs[1].hist(s.clip(upper=100), bins=50, log=True)
    axs[1].set(title="Todos los saltos (recortado en 100, eje log)", xlabel="salto entre cuadros")
    f.tight_layout()
    f.savefig(FIGURAS / "saltos.png", dpi=150)
    plt.close(f)


def main():
    TABLAS.mkdir(parents=True, exist_ok=True)
    c = cargar_cuadros()
    r = resumen(c)
    r.to_csv(TABLAS / "resumen_secuencias.csv")
    print("== Paso 1: resumen por secuencia ==")
    print(r.to_string())

    b = cargar_cajas(c)
    glob, por_seq = tamanos(b)
    glob.to_csv(TABLAS / "tamanos_cajas_global.csv")
    por_seq.to_csv(TABLAS / "tamanos_cajas_por_secuencia.csv")
    figura_tamanos(b)
    print(f"\n== Paso 2: tamaños de caja ({len(b)} cajas) ==")
    print(glob.to_string())
    print()
    print(por_seq.to_string())

    ps, cuant, sal = saltos(c)
    ps.to_csv(TABLAS / "saltos_por_secuencia.csv")
    figura_saltos(sal)
    print("\n== Paso 3: saltos entre cuadros ==")
    print(ps.to_string())
    print("\nCuantiles de saltos (todas las secuencias):")
    print(cuant.to_string())


if __name__ == "__main__":
    main()
