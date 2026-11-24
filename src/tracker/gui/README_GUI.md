# GUI del Tracker

Vive en `src/tracker/gui/`. Se abre con `uv run tracker` (`tracker.gui.app.ejecutar`).
Usa el formato común de canales de `tracker.canales`; los tubos son `canal_libre.CanalLibre` (un `Canal` que puede ser un cuadrilátero).

## Diseño y flujo en 4 pasos
La ventana guía a la persona: un cartel sobre el video dice qué hacer ahora y el panel derecho tiene 4 pasos numerados
(**1 Abre tu video · 2 Marca los tubos · 3 Cuenta los peces · 4 Revisa y exporta**); cada número se vuelve ✓ al completarse.
Los pasos 3 y 4 quedan siempre a la vista; los pasos 1 y 2 se desplazan. «Dispositivo» y «Modelo» están en la cabecera.
Se puede arrastrar un video a la ventana (o hacer clic en el área vacía del video) para abrirlo. Posición/tamaño (X, Y, ancho, alto)
del tubo están en «Posición y tamaño (avanzado)». Colores, tamaños y estilos viven en `tema.py` (no hay lógica allí).

## Uso
1. **Abrir video…** y recorrerlo con **▶ Reproducir** (Espacio) o arrastrando la barra.
2. **Dibujar tubo**: arrastra el mouse sobre el video (Esc cancela).
3. El tubo nuevo queda **en edición** (un clic sobre cualquier tubo lo vuelve a abrir): las **4 esquinas** (cuadritos blancos) se mueven de a una y dan forma
   al tubo (no se admite un tubo cruzado); con **Mayús** la esquina solo cambia el tamaño y conserva la forma. Arrastrar por dentro lo mueve; los círculos
   amarillos mueven las líneas **A** y **B** (zona de conteo; los peces avanzan de arriba hacia abajo y las líneas siguen la forma del tubo).
4. **Configuración del tubo** (panel derecho, se abre al hacer clic en un tubo): nombre, analizar (✔), líneas A/B (%), X, Y, ancho y alto.
   **Fijar**: Enter, clic fuera, elegir otro tubo o **✔ Listo**.
5. Marca/desmarca ✔ en la lista para elegir qué tubos se analizan (`activo` en el JSON).
6. **Guardar canales…** escribe el JSON del formato común (`<video>.canales.json`); **Cargar canales…** lo lee. Un tubo rectangular se guarda
   exactamente como siempre; uno deformado agrega `forma: "cuadrilatero"` y `puntos` (`canal_libre.py`).

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
Paso 3 y 4 del panel derecho: **⚙ Procesar video**, **Exportar resultados…**, **Ver resultados** (el dispositivo CPU/GPU está en la cabecera).
- **Procesar** corre `tracker.pipeline.procesar` en un hilo aparte: video con cajas e IDs, barra de progreso y
  conteo por canal en vivo (junto al nombre del tubo y en la lista; un tubo sin peces muestra 0). **✖ Cancelar** lo detiene.
  Solo se analizan los tubos marcados (✔). Mientras corre no se puede editar.
- **Exportar** escribe el formato común en `<carpeta elegida>/<video>_<perfil>/` y lo **valida** con `tracker.formato.validar`
  (ahí los tubos van como rectángulos: su caja envolvente, porque `tracker.canales.cargar_canales` aún no lee `puntos`). Además deja
  `<video>_<perfil>.json` (`exportar_json.py`): un solo archivo con la forma exacta de los tubos, el conteo, las trayectorias, el diagnóstico
  y, cuadro por cuadro, detecciones, cajas con ID y eventos. `exportar_json.leer_json` lo vuelve a leer como `Resultados`.
- Errores claros: sin video, sin tubos, ningún tubo marcado, pesos no encontrados, perfil no implementado, GPU no soportada,
  carpeta sin permiso de escritura, archivos que no cumplen el formato.
- Los canales vienen del Validador (`canales.json`): **Cargar canales…** los lee tal cual y se procesan sin cambiarlos.

## Modelo y líneas A/B
- La GUI procesa siempre con el perfil **variante**: YOLO26 (`weights/yolo26.pt`) y conteo **A → B** con histéresis.
  El perfil se define en `configs/perfiles/variante.yaml`; la constante `proceso.PERFIL` elige cuál se usa.
- Las líneas A y B de cada tubo se editan (círculos amarillos o panel) y **Restablecer líneas A/B** vuelve a los valores de `lineas.py`.
  Los tubos nuevos parten en **A = 60 %, B = 65 %**. La regla A → B solo cuenta a un pez que se vio **sobre A** y después llegó a B:
  con A muy arriba (antes 23 %) los peces que se detectan hacia la mitad del video ya están bajo A y no cuentan, y con B muy abajo
  (antes 77 %) no cuentan los que terminan antes. Calibración: `seq_0005` (peces seguidos desde el 10-43 % del alto del tubo hasta el
  67-95 %; con A entre 45 % y 65 % se cuentan los 6). Con pocos videos: conviene revisarla con otras secuencias y con YOLO26.
- Al **cargar canales** o al **procesar**, si alguna línea queda fuera de `lineas.RANGO_A` / `lineas.B_MAX` la GUI avisa y ofrece restablecerla.
  `lineas.EDITABLES = False` las deja fijas.
- Un `canales.json` cargado conserva sus líneas salvo que aceptes restablecerlas.
