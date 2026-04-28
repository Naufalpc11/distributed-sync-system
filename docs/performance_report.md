# Performance Report

## Method
Benchmark dijalankan melalui `benchmarks/load_test_scenarios.py` pada environment lokal.

Skenario yang diukur:
- `lock_acquire_release`
- `queue_enqueue_dequeue`
- `cache_set_get_invalidate`

Output mentah disimpan di `benchmarks/results.csv`.

## Results

| Skenario | Iterasi | Rata-rata (ms) | P95 (ms) | Minimum (ms) | Maksimum (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| lock_acquire_release | 5000 | 0.0007 | 0.0007 | 0.0006 | 0.0449 |
| queue_enqueue_dequeue | 2000 | 7.9950 | 9.2345 | 6.6406 | 16.6693 |
| cache_set_get_invalidate | 5000 | 0.0016 | 0.0017 | 0.0015 | 0.0417 |

## Interpretation
- Operasi lock sangat cepat karena mayoritas terjadi di memori.
- Operasi queue lebih lambat karena menulis ke SQLite dan mengelola metadata replikasi.
- Operasi cache tetap cepat; biaya invalidasi pada benchmark lokal sangat kecil.

## Notes
- Ini adalah microbenchmark lokal, bukan benchmark jaringan terdistribusi end-to-end.
- Untuk laporan akhir yang lebih kuat, tambahkan skenario failover leader atau uji 3-node dengan network delay.
- Nilai latensi yang sangat kecil pada lock/cache perlu dibaca sebagai baseline internal proses lokal, bukan representasi latensi produksi.
