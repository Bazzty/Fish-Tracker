# Comparación de trackers (T14)

Generado por `scripts/barrido_tracker.py` el 2026-11-22 19:44. Perfil `variante` (detector `weights/yolo26.pt`, conteo `histeresis`), 8 secuencias: seq_00015, seq_00016, seq_00032, seq_00033, seq_00037, seq_00041, seq_00055, seq_00061.

Criterio: 1) menor error de conteo con el detector, 2) mayor IDF1, 3) menos ID switches. La referencia es la línea simple aplicada a las trayectorias de DAT-02.

## Decisión

**`ocsort_buf15_iou0.1_min1`** (ocsort, lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=1): contó 135 de 137 peces (error 2), IDF1 93.0 %, 1 cambios de ID.

## Con el detector (resultado real)

| # | Configuración | Parámetros | IDF1 | IDSW | MOTA | FP | FN | Conteo | Referencia | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `ocsort_buf15_iou0.1_min1` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 93.0 % | 1 | 87.2 % | 30 | 173 | 135 | 137 | **2** |
| 2 | `ocsort_buf30_iou0.1_min1` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 93.0 % | 1 | 87.2 % | 30 | 173 | 135 | 137 | **2** |
| 3 | `ocsort_buf60_iou0.1_min1` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 92.8 % | 2 | 87.1 % | 30 | 173 | 135 | 137 | **2** |
| 4 | `ocsort_buf15_iou0.2_min1` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 91.8 % | 6 | 85.8 % | 28 | 192 | 132 | 137 | **5** |
| 5 | `ocsort_buf60_iou0.2_min1` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 91.4 % | 12 | 85.4 % | 28 | 192 | 132 | 137 | **5** |
| 6 | `ocsort_buf30_iou0.2_min1` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 91.4 % | 11 | 85.4 % | 28 | 193 | 132 | 137 | **5** |
| 7 | `ocsort_buf15_iou0.1_min3` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 83.2 % | 0 | 70.8 % | 30 | 434 | 128 | 137 | **9** |
| 8 | `ocsort_buf30_iou0.1_min3` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 83.2 % | 0 | 70.8 % | 30 | 434 | 128 | 137 | **9** |
| 9 | `ocsort_buf60_iou0.1_min3` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 83.1 % | 0 | 70.7 % | 30 | 436 | 127 | 137 | **10** |
| 10 | `ocsort_buf15_iou0.2_min3` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 81.7 % | 2 | 69.0 % | 28 | 463 | 122 | 137 | **15** |
| 11 | `ocsort_buf60_iou0.2_min3` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 81.4 % | 2 | 68.6 % | 28 | 469 | 121 | 137 | **16** |
| 12 | `ocsort_buf30_iou0.2_min3` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 81.4 % | 2 | 68.5 % | 28 | 471 | 121 | 137 | **16** |
| 13 | `botsort_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 87.6 % | 8 | 78.5 % | 33 | 300 | 118 | 137 | **19** |
| 14 | `botsort_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 87.6 % | 8 | 78.5 % | 33 | 300 | 118 | 137 | **19** |
| 15 | `bytetrack_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 62.8 % | 10 | 33.6 % | 383 | 662 | 117 | 137 | **20** |
| 16 | `botsort_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 87.2 % | 9 | 78.1 % | 27 | 312 | 116 | 137 | **21** |
| 17 | `botsort_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 87.2 % | 9 | 78.1 % | 27 | 312 | 116 | 137 | **21** |
| 18 | `bytetrack_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 62.8 % | 10 | 33.6 % | 383 | 662 | 116 | 137 | **21** |
| 19 | `bytetrack_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 63.1 % | 17 | 35.4 % | 349 | 659 | 115 | 137 | **22** |
| 20 | `bytetrack_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 63.1 % | 17 | 35.3 % | 350 | 660 | 115 | 137 | **22** |
| 21 | `botsort_reid_buf30` | track_buffer=30 | 82.0 % | 30 | 72.9 % | 19 | 382 | 110 | 137 | **27** |
| 22 | `botsort_reid_buf15` | track_buffer=15 | 82.2 % | 29 | 72.8 % | 19 | 384 | 109 | 137 | **28** |
| 23 | `botsort_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 82.3 % | 25 | 72.9 % | 16 | 389 | 108 | 137 | **29** |
| 24 | `botsort_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 82.2 % | 26 | 73.0 % | 16 | 387 | 108 | 137 | **29** |
| 25 | `bytetrack_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 63.2 % | 51 | 42.7 % | 215 | 644 | 106 | 137 | **31** |
| 26 | `bytetrack_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 63.5 % | 49 | 43.0 % | 211 | 646 | 105 | 137 | **32** |
| 27 | `deepsort_buf15` | max_age=15 | 65.7 % | 54 | 53.6 % | 31 | 652 | 91 | 137 | **46** |
| 28 | `deepsort_buf30` | max_age=30 | 65.3 % | 55 | 53.5 % | 32 | 652 | 91 | 137 | **46** |

## Con oráculo (cajas del GT: mide solo el tracker)

| # | Configuración | Parámetros | IDF1 | IDSW | MOTA | FP | FN | Conteo | Referencia | Error |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `ocsort_buf15_iou0.1_min1` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 95.1 % | 3 | 90.9 % | 0 | 142 | 135 | 137 | **2** |
| 2 | `ocsort_buf30_iou0.1_min1` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 95.1 % | 4 | 90.9 % | 0 | 141 | 135 | 137 | **2** |
| 3 | `ocsort_buf60_iou0.1_min1` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=1 | 95.1 % | 4 | 90.9 % | 0 | 141 | 135 | 137 | **2** |
| 4 | `ocsort_buf30_iou0.2_min1` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 93.5 % | 11 | 89.3 % | 0 | 159 | 133 | 137 | **4** |
| 5 | `ocsort_buf60_iou0.2_min1` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 93.4 % | 13 | 89.3 % | 0 | 157 | 133 | 137 | **4** |
| 6 | `ocsort_buf15_iou0.2_min1` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=1 | 93.7 % | 6 | 89.4 % | 0 | 162 | 132 | 137 | **5** |
| 7 | `ocsort_buf15_iou0.1_min3` | lost_track_buffer=15, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 85.6 % | 0 | 74.9 % | 0 | 399 | 127 | 137 | **10** |
| 8 | `ocsort_buf30_iou0.1_min3` | lost_track_buffer=30, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 85.6 % | 0 | 74.9 % | 0 | 399 | 127 | 137 | **10** |
| 9 | `ocsort_buf60_iou0.1_min3` | lost_track_buffer=60, minimum_iou_threshold=0.1, minimum_consecutive_frames=3 | 85.6 % | 0 | 74.9 % | 0 | 399 | 127 | 137 | **10** |
| 10 | `botsort_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 90.7 % | 12 | 84.8 % | 2 | 228 | 124 | 137 | **13** |
| 11 | `botsort_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 90.5 % | 14 | 84.6 % | 2 | 228 | 124 | 137 | **13** |
| 12 | `ocsort_buf15_iou0.2_min3` | lost_track_buffer=15, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 84.1 % | 2 | 72.9 % | 0 | 428 | 124 | 137 | **13** |
| 13 | `ocsort_buf30_iou0.2_min3` | lost_track_buffer=30, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 83.9 % | 2 | 72.7 % | 0 | 431 | 124 | 137 | **13** |
| 14 | `ocsort_buf60_iou0.2_min3` | lost_track_buffer=60, minimum_iou_threshold=0.2, minimum_consecutive_frames=3 | 83.9 % | 2 | 72.7 % | 0 | 432 | 124 | 137 | **13** |
| 15 | `bytetrack_buf30_mt0.95` | track_buffer=30, match_thresh=0.95 | 63.0 % | 14 | 33.4 % | 410 | 634 | 124 | 137 | **13** |
| 16 | `bytetrack_buf15_mt0.95` | track_buffer=15, match_thresh=0.95 | 62.9 % | 13 | 33.2 % | 412 | 636 | 123 | 137 | **14** |
| 17 | `bytetrack_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 64.2 % | 17 | 36.2 % | 377 | 619 | 122 | 137 | **15** |
| 18 | `botsort_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 89.4 % | 21 | 84.0 % | 0 | 233 | 121 | 137 | **16** |
| 19 | `botsort_buf30_mt0.9` | track_buffer=30, match_thresh=0.9 | 89.0 % | 24 | 83.8 % | 0 | 233 | 121 | 137 | **16** |
| 20 | `bytetrack_buf15_mt0.9` | track_buffer=15, match_thresh=0.9 | 64.2 % | 16 | 36.2 % | 377 | 620 | 120 | 137 | **17** |
| 21 | `botsort_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 88.3 % | 24 | 81.2 % | 0 | 274 | 115 | 137 | **22** |
| 22 | `botsort_reid_buf15` | track_buffer=15 | 88.2 % | 24 | 81.2 % | 0 | 275 | 115 | 137 | **22** |
| 23 | `botsort_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 88.0 % | 27 | 81.3 % | 0 | 270 | 115 | 137 | **22** |
| 24 | `botsort_reid_buf30` | track_buffer=30 | 87.8 % | 27 | 81.2 % | 0 | 271 | 115 | 137 | **22** |
| 25 | `bytetrack_buf30_mt0.8` | track_buffer=30, match_thresh=0.8 | 65.7 % | 47 | 43.0 % | 274 | 584 | 113 | 137 | **24** |
| 26 | `bytetrack_buf15_mt0.8` | track_buffer=15, match_thresh=0.8 | 65.8 % | 46 | 43.1 % | 271 | 586 | 111 | 137 | **26** |
| 27 | `deepsort_buf15` | max_age=15 | 68.4 % | 57 | 58.1 % | 0 | 609 | 93 | 137 | **44** |
| 28 | `deepsort_buf30` | max_age=30 | 68.3 % | 58 | 58.1 % | 0 | 608 | 92 | 137 | **45** |

Si un tracker acierta con oráculo y falla con el detector, la falla es del detector, no del tracker.
