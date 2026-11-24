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

Calibrada con seq_0005 (6 peces, 52 cuadros): los peces empiezan a seguirse (ID estable) entre el 10 % y el
43 % del alto del tubo y terminan entre el 67 % y el 95 %. Con A entre 45 % y 65 % se cuentan los 6; con A = 36 %
solo 3, porque 3 peces ya estaban bajo la línea cuando empezó su seguimiento. Como hay peces que se detectan hacia
la mitad del video, A parte en la zona alta de ese rango (60 %) y B justo debajo (65 %, por encima de donde termina
el pez más corto: 67 %).
Es una calibración con pocos videos: conviene revisarla con otras secuencias (en la GUI, «Restablecer líneas A/B»
vuelve a estos valores).

Un canales.json cargado conserva sus líneas; si quedan fuera de RANGO_A / B_MAX, la GUI avisa y ofrece restablecerlas.
"""
LINEA_A = 0.60
LINEA_B = 0.65
EDITABLES = True  # True: se pueden mover las líneas A y B (círculos amarillos y panel); False: quedan fijas

RANGO_A = (0.45, 0.65)  # A fuera de este rango: pierde peces que empiezan a seguirse abajo o que terminan arriba
B_MAX = 0.67            # B bajo este valor: los peces más cortos de la calibración todavía llegan a B


def fuera_de_rango(linea_a: float, linea_b: float) -> bool:
    """¿Las líneas quedaron donde el conteo suele perder peces?"""
    return not (RANGO_A[0] <= linea_a <= RANGO_A[1]) or linea_b > B_MAX
