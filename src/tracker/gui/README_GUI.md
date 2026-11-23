# GUI del Tracker

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
Botón **Ver resultados** (barra de arriba): muestra el último procesamiento o, si no hay, deja abrir una carpeta del formato común (p. ej. `docs/ejemplo_formato`) con `tracker.formato.leer`.
- **Conteo por canal**: tabla, barras y lista de eventos de conteo (un tubo vacío = 0).
- **Diagnóstico del seguimiento** (`diagnostico.py`): clasifica *caja intermitente*, *ID perdido* e *ID nuevo*
  a partir de `trayectorias.csv`, enlaza fragmentaciones probables (ID perdido → ID nuevo cercano) y exporta CSV.
  Es una heurística sin etiquetas de referencia; los umbrales están en `diagnostico.Params`.

## Procesar el video con avance en vivo (T15) y exportar (T17)
Barra de herramientas superior: **Perfil** (base / variante), **⚙ Procesar video**, **Exportar resultados…**, **Ver resultados**.
- **Procesar** corre `tracker.pipeline.procesar` en un hilo aparte: video con cajas e IDs, barra de progreso y
  conteo por canal en vivo (junto al nombre del tubo y en la lista; un tubo sin peces muestra 0). **✖ Cancelar** lo detiene.
  Solo se analizan los tubos marcados (✔). Mientras corre no se puede editar.
- **Exportar** escribe el formato común en `<carpeta elegida>/<video>_<perfil>/` y lo **valida** con `tracker.formato.validar`.
- Errores claros: sin video, sin tubos, ningún tubo marcado, pesos no encontrados, perfil no implementado, GPU no soportada,
  carpeta sin permiso de escritura, archivos que no cumplen el formato.
- Los canales vienen del Validador (`canales.json`): **Cargar canales…** los lee tal cual y se procesan sin cambiarlos.

## Modelo y líneas A/B
- La GUI procesa siempre con el perfil **variante**: YOLO26 (`weights/yolo26.pt`) y conteo **A → B** con histéresis.
  El perfil se define en `configs/perfiles/variante.yaml`; la constante `proceso.PERFIL` elige cuál se usa.
- Las líneas A y B de cada tubo se editan (círculos amarillos o panel). Los tubos nuevos parten en **A = 55 %, B = 65 %**
  (`lineas.py`), valores calibrados con `seq_0005` (6 peces, perfil base): con A entre 45 % y 65 % se cuentan los 6.
  Es una calibración con un solo video; con YOLO26 conviene revisarla. `lineas.EDITABLES = False` las deja fijas.
- Un `canales.json` cargado (p. ej. el del Validador) conserva sus propias líneas.
