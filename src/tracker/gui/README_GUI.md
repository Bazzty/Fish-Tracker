# GUI del Tracker (Misión 1)

Vive en `src/tracker/gui/`. Se abre con `uv run tracker` (`tracker.gui.app.ejecutar`).
Usa el formato común de canales de `tracker.canales` (`Canal`, `guardar_canales`, `cargar_canales`).

## Uso
1. **Abrir video…** y recorrerlo con **▶ Reproducir** (Espacio) o arrastrando la barra.
2. **Dibujar tubo**: arrastra el mouse sobre el video (Esc cancela).
3. El tubo nuevo queda **en edición** (un clic sobre cualquier tubo lo vuelve a abrir): cuadritos blancos para cambiar ancho/alto, arrastrar por dentro para moverlo,
   círculos amarillos para mover las líneas **A** y **B** (zona de conteo; los peces avanzan de arriba hacia abajo).
4. **Configuración del tubo** (panel derecho, se abre al hacer clic en un tubo): nombre, analizar (✔), líneas A/B (%), X, Y, ancho y alto.
   **Fijar**: Enter, clic fuera, elegir otro tubo o **✔ Listo**.
5. Marca/desmarca ✔ en la lista para elegir qué tubos se analizan (`activo` en el JSON).
6. **Guardar canales…** escribe el JSON del formato común (`<video>.canales.json`); **Cargar canales…** lo lee.

## Integración
- `MainWindow.selected_channels()` devuelve los `Canal` con `activo=True`.
- `uv run tracker procesar --video v.mp4 --canales v.canales.json --salida outputs/v` consume el mismo JSON.

## Resultados (T10) y diagnóstico del seguimiento (T11)
Menú **Resultados → Abrir resultados… / Resultados de ejemplo** (lee una carpeta del formato común con `tracker.formato.leer`).
- **Conteo por canal**: tabla, barras y lista de eventos de conteo (un tubo vacío = 0).
- **Diagnóstico del seguimiento** (`diagnostico.py`): clasifica *caja intermitente*, *ID perdido* e *ID nuevo*
  a partir de `trayectorias.csv`, enlaza fragmentaciones probables (ID perdido → ID nuevo cercano) y exporta CSV.
  Es una heurística sin etiquetas de referencia; los umbrales están en `diagnostico.Params`.
