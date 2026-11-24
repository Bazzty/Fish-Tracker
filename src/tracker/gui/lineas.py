"""Zona de conteo de los tubos: líneas A (entrada) y B (salida), como fracción del alto desde arriba.

Valores INICIALES de los tubos nuevos; se pueden editar (EDITABLES = True).

Cómo cuenta cada regla (docs/formato_comun.md):
  - línea simple: el pez cuenta al cruzar A hacia abajo, y solo si antes se vio SOBRE A.
  - histéresis (variante, la que usa la GUI): el pez queda «armado» al verse sobre A y cuenta al llegar a B.
En las dos, un pez que aparece por primera vez más abajo de A nunca queda armado y no se cuenta. Y con la
histéresis, un pez cuya trayectoria termina antes de llegar a B tampoco. Por eso:
  - A no puede quedar muy arriba (p. ej. 23 %): los peces que se detectan «por la mitad del video» ya
    estarían bajo A. Tiene que quedar bajo el punto donde empiezan a seguirse los peces.
  - B no puede quedar muy abajo (p. ej. 77 %): los peces que terminan antes no llegan a B.

Elegidas en validación (8 secuencias de DAT-02, 137 peces; YOLO26 + OC-SORT + histéresis): se barrió A del 30 al
70 % y B de A+5 a A+20 %. El error es plano: con A entre 35 % y 70 % y B hasta 80 % se cuentan 135 de 137 (error 2);
con A = 30 % se cuentan 133 y con B >= 85 % el conteo cae (108 con A = 70 %, B = 90 %). Se usa el centro de esa
zona, A = 50 % y B = 60 %, que además son las líneas de configs/canales_*.json: la GUI y la CLI cuentan igual.
Test no se usó para elegirlas.

Un canales.json cargado conserva sus líneas; si quedan fuera de RANGO_A / B_MAX, la GUI avisa y ofrece restablecerlas.
"""
LINEA_A = 0.50
LINEA_B = 0.60
EDITABLES = True  # True: se pueden mover las líneas A y B (círculos amarillos y panel); False: quedan fijas

RANGO_A = (0.35, 0.70)  # zona plana del barrido en val: fuera de ella el conteo empieza a perder peces
B_MAX = 0.80            # con B >= 85 % los peces que terminan antes ya no llegan a B


def fuera_de_rango(linea_a: float, linea_b: float) -> bool:
    """¿Las líneas quedaron donde el conteo suele perder peces?"""
    return not (RANGO_A[0] <= linea_a <= RANGO_A[1]) or linea_b > B_MAX
