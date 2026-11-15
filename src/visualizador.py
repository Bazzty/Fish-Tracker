import csv
import os
import cv2

import sys
from pathlib import Path

# 1. Secuencia a revisar: uv run python src/visualizador.py seq_0003 (por defecto seq_0002)
RAIZ = Path(__file__).resolve().parents[1]
seq_path = str(RAIZ / "data" / (sys.argv[1] if len(sys.argv) > 1 else "seq_0002"))
images_dir = os.path.join(seq_path, "images")
labels_dir = os.path.join(seq_path, "labels")

# 2. Obtener lista de imágenes VÁLIDAS
todos_los_archivos = os.listdir(images_dir)
print(f"Archivos totales en la carpeta: {len(todos_los_archivos)}")

# Aceptamos .jpg, .jpeg, en mayúsculas o minúsculas
image_files = [
    f
    for f in todos_los_archivos
    if f.lower().endswith((".jpg", ".jpeg")) and not f.startswith("._")
]
image_files.sort()

total_cuadros = len(image_files)
print(f"Se encontraron {total_cuadros} cuadros válidos.")

# --- NAVEGACIÓN INTERACTIVA (BUCLE WHILE) ---
idx = 0

# Variables para estadísticas globales
total_cajas_global = 0
anchos_cajas = []
altos_cajas = []
cuadros_con_peces_set = set()  # Guarda índices de cuadros que tienen al menos 1 pez
datos_exportar = [["Frame", "Cantidad_Salmones"]]

print("\n--- CONTROLES DEL VISUALIZADOR ---")
print(" Flecha DERECHA / D / Espacio : Avanzar 1 cuadro")
print(" Flecha IZQUIERDA / A         : Retroceder 1 cuadro")
print(" Q / ESC                      : Salir del visualizador\n")

while 0 <= idx < total_cuadros:
    img_name = image_files[idx]
    img_path = os.path.join(images_dir, img_name)

    nombre_base = os.path.splitext(img_name)[0]
    label_name = nombre_base + ".txt"
    label_path = os.path.join(labels_dir, label_name)

    # Leer la imagen
    img = cv2.imread(img_path)
    if img is None:
        print(f"No se pudo leer la imagen: {img_path}")
        idx += 1
        continue

    alto, ancho, _ = img.shape
    cajas_en_este_cuadro = 0

    # 3. Leer las etiquetas YOLO y dibujar cajas para este fotograma
    if os.path.exists(label_path):
        with open(label_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if len(parts) == 5:
                    clase, x_c, y_c, w, h = map(float, parts)

                    # Desnormalizar YOLO
                    x_centro = int(x_c * ancho)
                    y_centro = int(y_c * alto)
                    ancho_caja = int(w * ancho)
                    alto_caja = int(h * alto)

                    x_min = int(x_centro - ancho_caja / 2)
                    y_min = int(y_centro - alto_caja / 2)

                    # Dibujar el rectángulo
                    cv2.rectangle(
                        img,
                        (x_min, y_min),
                        (x_min + ancho_caja, y_min + alto_caja),
                        (0, 255, 0),
                        2,
                    )

                    cajas_en_este_cuadro += 1

    # Dibujar la línea virtual de conteo
    porcentaje_linea = 0.50  # Puedes probar con 0.40, 0.50 o 0.60
    y_linea = int(alto * porcentaje_linea)
    cv2.line(img, (0, y_linea), (ancho, y_linea), (0, 255, 255), 2)

    # Texto de la línea virtual
    cv2.putText(
        img,
        f"Linea Virtual ({int(porcentaje_linea * 100)}%)",
        (10, y_linea - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2,
    )

    # Texto de cabecera con el número de frame y salmones en pantalla
    info_frame = f"Frame {idx + 1}/{total_cuadros} ({img_name}) | Salmones en cuadro: {cajas_en_este_cuadro}"
    cv2.putText(
        img,
        info_frame,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )

    # 4. Mostrar la imagen en pantalla
    cv2.imshow("Visualizador de Salmones - Interactivo", img)

    # Capturar tecla (Soporta flechas extendidas en Windows)
    key = cv2.waitKeyEx(0)

    # --- LÓGICA DE CONTROL DE TECLADO ---
    # Q o ESC (27) para salir
    if key == 27 or (key & 0xFF) in [27, ord("q"), ord("Q")]:
        print("Visualización finalizada por el usuario (ESC / Q).")
        break

    # Flecha IZQUIERDA o tecla 'A': Retroceder
    elif key in [2424832, 81, 65361, 37, ord("a"), ord("A")]:
        if idx > 0:
            idx -= 1
        else:
            print("Ya estás en el primer fotograma (Frame 1).")

    # Flecha DERECHA, 'D', Espacio o Enter: Avanzar
    elif key in [2555904, 83, 65363, 39, ord("d"), ord("D"), 32, 13]:
        if idx < total_cuadros - 1:
            idx += 1
        else:
            print("Llegaste al último fotograma.")
            break
    else:
        # Cualquier otra tecla avanza 1 cuadro por defecto
        if idx < total_cuadros - 1:
            idx += 1
        else:
            break

cv2.destroyAllWindows()

# --- 5. SECCIÓN DE ESTADÍSTICAS Y EXPORTACIÓN ---
# Descomentar cuando quieras volver a generar los CSV acumulativos:
# os.makedirs("statistics", exist_ok=True)
# csv_filename = os.path.join("statistics", "estadisticas_seq_0002.csv")
# with open(csv_filename, mode="w", newline="") as file:
#     writer = csv.writer(file)
#     writer.writerows(datos_exportar)
