# GUI del Tracker (Misión 1)

Vive en `src/tracker/gui/`. Se abre con `uv run tracker` (`tracker.gui.app.ejecutar`).
Usa el formato común de canales de `tracker.canales` (`Canal`, `guardar_canales`, `cargar_canales`).

## Uso
1. **Abrir video…** y recorrerlo con **▶ Reproducir** (Espacio), **◀ / ▶ Cuadro** (← →) o la barra.
2. **Dibujar tubo**: arrastra el mouse sobre el video (Esc cancela).
3. El tubo nuevo queda **en edición**: cuadritos blancos para cambiar ancho/alto, arrastrar por dentro para moverlo,
   círculos amarillos para mover las líneas **A** y **B** (zona de conteo; los peces avanzan de arriba hacia abajo).
4. **Fijar**: Enter, clic fuera, elegir otro tubo o el botón. Para editar de nuevo: doble clic o **Editar tubo**.
5. Marca/desmarca ✔ en la lista para elegir qué tubos se analizan (`activo` en el JSON).
6. **Guardar canales…** escribe el JSON del formato común (`<video>.canales.json`); **Cargar canales…** lo lee.

## Integración
- `MainWindow.selected_channels()` devuelve los `Canal` con `activo=True`.
- `uv run tracker procesar --video v.mp4 --canales v.canales.json --salida outputs/v` consume el mismo JSON.
