"""Zona de conteo de los tubos: líneas A (entrada) y B (salida), como fracción del alto desde arriba.

Valores INICIALES de los tubos nuevos; se pueden editar (EDITABLES = True).

Calibrada con seq_0005 (6 peces, 52 cuadros), con la regla de línea simple: un pez cuenta
si se ve sobre la línea A y después en A o más abajo. En esa secuencia:
  - los peces empiezan a seguirse (ID estable) entre el 10 % y el 43 % del alto del tubo;
  - los peces terminan entre el 67 % y el 95 % del alto;
  - con A entre 45 % y 65 % se cuentan los 6 peces; con A = 36 % (antes) solo 3, porque 3 peces
    ya estaban bajo la línea cuando empezó su seguimiento.
A = 55 % es el centro de ese rango (±10 % de margen). B = 65 % queda por debajo de A y todavía por encima de
donde termina el pez más corto (67 %), así la variante (histéresis A → B) también cuenta los 6.
Es una calibración con UN video: conviene revisarla con otras secuencias.

Un canales.json que traiga el Validador se respeta tal cual (el Tracker no redefine los canales):
estos valores solo se usan como punto de partida de los tubos que se dibujan en la GUI.
"""
LINEA_A = 0.23
LINEA_B = 0.77
EDITABLES = True  # True: se pueden mover las líneas A y B (círculos amarillos y panel); False: quedan fijas
