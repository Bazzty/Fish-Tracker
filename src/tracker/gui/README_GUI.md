# GUI del Tracker (Misión 1)

Copiar esta carpeta a `src/tracker/gui/` del repo.

## Dependencias (pyproject.toml)
    uv add PySide6 opencv-python-headless

(Se usa la versión *headless* de OpenCV para que no choque con los plugins de Qt.)

## Comando `uv run tracker` 
En `[project.scripts]`:

    tracker = "tracker.gui.app:main"

## Uso
1. **Abrir video…** y navega con la barra de cuadros.
2. **Dibujar tubo**: clic para añadir puntos; Enter o clic en el primer punto cierra; clic derecho deshace; Esc cancela.
3. Marca/desmarca los tubos a analizar en la lista (los no marcados se ven punteados).
4. **Guardar canales…** genera `<video>.channels.json`.

## Formato del JSON (coordenadas en píxeles del video)
    {
      "version": 1,
      "video": "video1.mp4",
      "frame_size": [1920, 1080],
      "channels": [
        {"id": 1, "name": "Tubo 1", "selected": true, "points": [[x, y], ...]}
      ]
    }

## Integración
`MainWindow.selected_channels()` devuelve los `Channel` marcados (polígonos) para el conteo.

## Dibujar y editar tubos
- **Dibujar tubo (rectángulo)**: arrastra el mouse sobre el video.
- **Dibujar punto a punto (opcional)**: polígono libre (Enter o clic en el primer punto cierra).
- Al elegir un tubo (en la lista o con clic sobre él en el video) aparecen cuadritos blancos:
  rectángulo → 8 manillas para cambiar ancho/alto; polígono → un cuadrito por vértice.
  Arrastrar por dentro mueve el tubo completo.
- En el JSON cada canal lleva `"kind": "rect" | "polygon"` (los rectángulos guardan 4 puntos).

## Editar vs. fijar
- Un tubo recién dibujado queda **en edición** (cuadritos blancos). Se **fija** con Enter, clic fuera, elegir otro tubo o el botón «Fijar tubo».
- Un tubo fijo no se puede mover por accidente. Para modificarlo: doble clic sobre él o botón «Editar tubo».
- Al cargar un JSON, todos los tubos quedan fijos.
