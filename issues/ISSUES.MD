## Detecciones defectuosas (YOLO11)

Con el detector YOLO11 del Lab 15 (`weights/best.pt`) hay cuadros donde no se detectan peces.

### Ejemplo: seq_00015, BoT-SORT

- Cuadro 86: el detector ve al pez.
- Cuadros 87 y 88: el detector no lo ve, por lo que el seguimiento tampoco.
- Cuadro 89: el detector lo vuelve a ver y el seguimiento le asigna un ID nuevo, como si fuera otro pez.

Las posibles causas son malas anotaciones o un entrenamiento defectuoso.

Las capturas se quitaron del repositorio porque los cuadros del dataset son confidenciales. Para revisarlas, correr `uv run tracker evaluar-seguimiento --seq seq_00015 --perfil base --trackers configs/botsort.yaml` y luego `uv run python scripts/video_seguimiento.py seq_00015 --tracker botsort --perfil base`.

**Estado:** el detector YOLO26 (`weights/yolo26.pt`, perfil `variante`) sube el recall en validación de 0,8904 a 0,9673 ([comparación](../resultados/tablas/yolo11_vs_yolo26.md)), y la regla de dos líneas con herencia evita que un ID nuevo cuente el mismo pez dos veces.
