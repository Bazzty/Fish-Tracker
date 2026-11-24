LINEA_A = 0.60
LINEA_B = 0.65
EDITABLES = True  # True: se pueden mover las líneas A y B (círculos amarillos y panel); False: quedan fijas

RANGO_A = (0.45, 0.65)  # A fuera de este rango: pierde peces que empiezan a seguirse abajo o que terminan arriba
B_MAX = 0.67            # B bajo este valor: los peces más cortos de la calibración todavía llegan a B


def fuera_de_rango(linea_a: float, linea_b: float) -> bool:
    """¿Las líneas quedaron donde el conteo suele perder peces?"""
    return not (RANGO_A[0] <= linea_a <= RANGO_A[1]) or linea_b > B_MAX
