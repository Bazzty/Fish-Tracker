## Detección defectuosas

Hay casos con el modelo de detección actual de Yolo11.pt donde se salta/no detecta pescados en los fotogramas.

### Ejemplo Seq_0015:

- BOTSORT:  
*Frame86:* Detector va bien.  
![alt text](./frame86.png)  
*Frame87:* Detector no ve este, por lo que seguimiento tampoco.  
![alt text](./frame87.png)  
*Frame88:*  Detector de nuevo no detecta al pez.
![alt text](./frame88.png)  
*Frame89:* El detector por fin lo ve, y el seguimiento vuelve, pensando que es un pez nuevo.  
![alt text](./frame89.png)  

Las posibles causas son malas anotaciones, o entrenamiento defectuoso (revisar parametros de entrenamiento).