# Comparación de trackers (T14): test

Generado por `scripts/barrido_tracker.py` el 2026-11-23 10:20. Perfil `variante` (detector `weights/yolo26.pt`, conteo `histeresis`), 9 secuencias de test: seq_00010, seq_00011, seq_00012, seq_00020, seq_00021, seq_00025, seq_00031, seq_00036, seq_00046.

Criterio: 1) menor error de conteo con el detector, 2) mayor IDF1, 3) menos ID switches. La referencia es la línea simple aplicada a las trayectorias de DAT-02.

## Decisión

**`ocsort_buf60_iou0.1_min1`** (ocsort, lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=1): contó 131 de 132 peces (error 1), IDF1 93.3 %, 4 cambios de ID.

## Con el detector (resultado real)

| # | Configuración | Parámetros | IDF1 | IDSW | MOTA | FP | FN | Conteo | Referencia | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `ocsort_buf60_iou0.1_min1` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 93.3 % | 4 | 87.5 % | 52 | 135 | 131 | 132 | **1** |
| 2 | `ocsort_buf30_iou0.1_min1` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 93.2 % | 4 | 87.4 % | 52 | 137 | 131 | 132 | **1** |
| 3 | `ocsort_buf15_iou0.1_min1` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 93.2 % | 4 | 87.3 % | 52 | 138 | 131 | 132 | **1** |
| 4 | `ocsort_buf15_iou0.2_min1` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 92.6 % | 6 | 86.4 % | 53 | 149 | 131 | 132 | **1** |
| 5 | `ocsort_buf30_iou0.2_min1` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 92.0 % | 10 | 86.2 % | 53 | 148 | 131 | 132 | **1** |
| 6 | `ocsort_buf60_iou0.2_min1` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 91.0 % | 15 | 85.8 % | 53 | 150 | 131 | 132 | **1** |
| 7 | `ocsort_buf60_iou0.1_min3` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 84.3 % | 1 | 72.1 % | 47 | 379 | 126 | 132 | **6** |
| 8 | `ocsort_buf30_iou0.1_min3` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 84.2 % | 1 | 72.0 % | 47 | 381 | 125 | 132 | **7** |
| 9 | `ocsort_buf15_iou0.1_min3` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 84.1 % | 1 | 71.9 % | 47 | 382 | 125 | 132 | **7** |
| 10 | `ocsort_buf15_iou0.2_min3` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 83.6 % | 1 | 71.1 % | 45 | 397 | 124 | 132 | **8** |
| 11 | `ocsort_buf30_iou0.2_min3` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 83.2 % | 2 | 70.6 % | 45 | 403 | 124 | 132 | **8** |
| 12 | `ocsort_buf60_iou0.2_min3` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 82.2 % | 4 | 69.8 % | 45 | 414 | 123 | 132 | **9** |
| 13 | `botsort_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 88.1 % | 9 | 79.6 % | 51 | 252 | 118 | 132 | **14** |
| 14 | `botsort_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 88.1 % | 9 | 79.6 % | 51 | 252 | 118 | 132 | **14** |
| 15 | `bytetrack_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 56.2 % | 14 | 19.7 % | 510 | 707 | 118 | 132 | **14** |
| 16 | `bytetrack_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 56.2 % | 14 | 19.7 % | 510 | 707 | 118 | 132 | **14** |
| 17 | `botsort_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 88.0 % | 10 | 78.8 % | 51 | 264 | 117 | 132 | **15** |
| 18 | `botsort_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 88.0 % | 10 | 78.8 % | 51 | 264 | 117 | 132 | **15** |
| 19 | `bytetrack_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 56.6 % | 15 | 21.9 % | 472 | 710 | 114 | 132 | **18** |
| 20 | `bytetrack_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 56.6 % | 15 | 21.9 % | 472 | 710 | 114 | 132 | **18** |
| 21 | `botsort_reid_buf15` | track_buffer=15 | 83.9 % | 28 | 74.7 % | 39 | 320 | 110 | 132 | **22** |
| 22 | `botsort_reid_buf30` | track_buffer=30 | 83.9 % | 28 | 74.7 % | 39 | 320 | 110 | 132 | **22** |
| 23 | `botsort_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 83.9 % | 26 | 74.8 % | 36 | 324 | 110 | 132 | **22** |
| 24 | `botsort_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 83.9 % | 26 | 74.8 % | 36 | 324 | 110 | 132 | **22** |
| 25 | `bytetrack_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 57.8 % | 63 | 33.6 % | 302 | 653 | 108 | 132 | **24** |
| 26 | `bytetrack_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 57.9 % | 57 | 33.2 % | 303 | 663 | 107 | 132 | **25** |
| 27 | `deepsort_buf15` | max_age=15 | 64.1 % | 73 | 50.8 % | 58 | 623 | 90 | 132 | **42** |
| 28 | `deepsort_buf30` | max_age=30 | 63.9 % | 74 | 50.7 % | 59 | 622 | 90 | 132 | **42** |

## Con oráculo (cajas del GT: mide solo el tracker)

| # | Configuración | Parámetros | IDF1 | IDSW | MOTA | FP | FN | Conteo | Referencia | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `ocsort_buf60_iou0.1_min1` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 95.0 % | 2 | 91.0 % | 0 | 136 | 131 | 132 | **1** |
| 2 | `ocsort_buf15_iou0.1_min1` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 95.0 % | 2 | 90.9 % | 0 | 137 | 131 | 132 | **1** |
| 3 | `ocsort_buf30_iou0.1_min1` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 95.0 % | 2 | 90.9 % | 0 | 137 | 131 | 132 | **1** |
| 4 | `ocsort_buf15_iou0.2_min1` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 94.4 % | 4 | 89.8 % | 0 | 152 | 129 | 132 | **3** |
| 5 | `ocsort_buf30_iou0.2_min1` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 94.2 % | 6 | 89.8 % | 0 | 150 | 129 | 132 | **3** |
| 6 | `ocsort_buf60_iou0.2_min1` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 93.2 % | 15 | 89.5 % | 0 | 146 | 128 | 132 | **4** |
| 7 | `botsort_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 92.0 % | 12 | 85.6 % | 3 | 205 | 125 | 132 | **7** |
| 8 | `botsort_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 92.0 % | 12 | 85.6 % | 3 | 205 | 125 | 132 | **7** |
| 9 | `ocsort_buf60_iou0.1_min3` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 85.7 % | 0 | 75.1 % | 0 | 381 | 125 | 132 | **7** |
| 10 | `ocsort_buf15_iou0.1_min3` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 85.7 % | 0 | 75.1 % | 0 | 382 | 125 | 132 | **7** |
| 11 | `ocsort_buf30_iou0.1_min3` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 85.7 % | 0 | 75.1 % | 0 | 382 | 125 | 132 | **7** |
| 12 | `botsort_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 91.3 % | 14 | 84.9 % | 3 | 214 | 124 | 132 | **8** |
| 13 | `botsort_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 91.3 % | 14 | 84.9 % | 3 | 214 | 124 | 132 | **8** |
| 14 | `bytetrack_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 58.9 % | 13 | 24.9 % | 459 | 678 | 123 | 132 | **9** |
| 15 | `bytetrack_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 58.9 % | 13 | 24.9 % | 459 | 678 | 123 | 132 | **9** |
| 16 | `ocsort_buf15_iou0.2_min3` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 84.9 % | 0 | 73.8 % | 0 | 402 | 122 | 132 | **10** |
| 17 | `ocsort_buf30_iou0.2_min3` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 84.8 % | 0 | 73.6 % | 0 | 404 | 121 | 132 | **11** |
| 18 | `ocsort_buf60_iou0.2_min3` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 84.1 % | 2 | 72.9 % | 0 | 413 | 120 | 132 | **12** |
| 19 | `bytetrack_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 60.1 % | 22 | 28.7 % | 413 | 658 | 119 | 132 | **13** |
| 20 | `bytetrack_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 60.1 % | 22 | 28.7 % | 413 | 658 | 119 | 132 | **13** |
| 21 | `botsort_reid_buf15` | track_buffer=15 | 87.2 % | 36 | 80.8 % | 1 | 257 | 118 | 132 | **14** |
| 22 | `botsort_reid_buf30` | track_buffer=30 | 87.2 % | 36 | 80.8 % | 1 | 257 | 118 | 132 | **14** |
| 23 | `botsort_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 87.1 % | 38 | 80.5 % | 1 | 259 | 118 | 132 | **14** |
| 24 | `botsort_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 87.1 % | 38 | 80.5 % | 1 | 259 | 118 | 132 | **14** |
| 25 | `bytetrack_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 62.6 % | 59 | 38.8 % | 286 | 593 | 117 | 132 | **15** |
| 26 | `bytetrack_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 62.5 % | 59 | 38.6 % | 283 | 599 | 115 | 132 | **17** |
| 27 | `deepsort_buf15` | max_age=15 | 64.8 % | 60 | 53.9 % | 0 | 646 | 86 | 132 | **46** |
| 28 | `deepsort_buf30` | max_age=30 | 64.6 % | 61 | 53.8 % | 0 | 646 | 86 | 132 | **46** |

Si un tracker acierta con oráculo y falla con el detector, la falla es del detector, no del tracker.
