# Distributed Sync System

Implementasi sistem sinkronisasi terdistribusi menggunakan Python dengan konsensus Raft serta pengelolaan lock, queue, dan cache lintas node.

## Features
- Pemilihan pemimpin (leader election) berbasis Raft.
- Pengelola lock terdistribusi (shared dan exclusive lock).
- Sistem antrean (queue) terdistribusi dengan penyimpanan SQLite.
- Koherensi cache dengan invalidasi antar node.
- Dokumentasi API OpenAPI/Swagger.
- Penerapan multi-node berbasis Docker.

## Quick Start

### 1. Setup Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 1b. Environment Template

File `.env.example` disediakan sebagai template konfigurasi. Jika ingin memakai environment variable, salin file tersebut menjadi `.env`, lalu sesuaikan nilainya.

### 1c. Run with `.env`

```bash
copy .env.example .env
```

Contoh isi `.env`:

```env
NODE_ID=node1
HOST=localhost
ADVERTISE_HOST=localhost
PORT=8001
PEERS=localhost:8002,localhost:8003
```

Jalankan node:

```bash
python main.py --env-file .env
```

Jika ingin menjalankan 3 node dengan file `.env` terpisah:

```bash
python main.py --env-file .env.node1
python main.py --env-file .env.node2
python main.py --env-file .env.node3
```

Argumen CLI tetap bisa dipakai dan akan menimpa nilai dari `.env`.

### 2. Run 3 Nodes Manually

Terminal 1:
```bash
python main.py --id node1 --port 8001 --peers localhost:8002 localhost:8003
```

Terminal 2:
```bash
python main.py --id node2 --port 8002 --peers localhost:8001 localhost:8003
```

Terminal 3:
```bash
python main.py --id node3 --port 8003 --peers localhost:8001 localhost:8002
```

Tunggu sampai salah satu node menampilkan log `Became LEADER`.

### 3. Manual End-to-End Demo

Urutan demo yang direkomendasikan saat presentasi:

1. Aktifkan virtual environment dan install dependency.
2. Jalankan 3 node di 3 terminal terpisah.
3. Pastikan leader sudah terpilih (`Became LEADER`).
4. Uji lock.
5. Uji queue.
6. Uji cache coherence.
7. Hentikan semua node dengan `Ctrl + C`.

Uji lock:

```powershell
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"demo-lock\",\"node_id\":\"node1\"}'
curl.exe -X GET http://localhost:8003/lock/status
curl.exe -X POST http://localhost:8001/lock/release -H "Content-Type: application/json" -d '{\"resource\":\"demo-lock\",\"node_id\":\"node1\"}'
```

Uji queue:

```powershell
curl.exe -X POST http://localhost:8002/queue/enqueue -H "Content-Type: application/json" -d '{\"item\":\"job-1\",\"node_id\":\"node1\"}'
curl.exe -X GET http://localhost:8001/queue/status
curl.exe -X POST http://localhost:8002/queue/dequeue -H "Content-Type: application/json" -d '{\"node_id\":\"node1\"}'
```

Uji cache coherence:

```powershell
curl.exe -X POST http://localhost:8001/cache/set -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"value\":{\"name\":\"naufal\"},\"node_id\":\"node1\"}'
curl.exe -X GET "http://localhost:8002/cache/get?key=user:1"
curl.exe -X GET http://localhost:8003/cache/status
curl.exe -X POST http://localhost:8001/cache/delete -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"node_id\":\"node1\"}'
```

### 4. Run with Docker

Untuk demo tanpa membuka 3 terminal manual:

```bash
docker compose up --build
```

Setelah container berjalan, endpoint bisa dipakai seperti demo manual.

Contoh:

```powershell
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"docker-lock\",\"node_id\":\"node1\"}'
curl.exe -X POST http://localhost:8002/queue/enqueue -H "Content-Type: application/json" -d '{\"item\":\"docker-job\",\"node_id\":\"node1\"}'
curl.exe -X POST http://localhost:8001/cache/set -H "Content-Type: application/json" -d '{\"key\":\"docker:key\",\"value\":{\"active\":true},\"node_id\":\"node1\"}'
```

Stop container:

```bash
docker compose down
```

### 5. Feature B Bonus: Geo-Distributed Demo

Bonus ini bisa didemokan lewat Docker Compose dengan simulasi latency antar region.

Variabel yang dipakai:

- `REGION`: region node saat ini.
- `PEER_REGIONS`: pemetaan peer ke region.
- `LATENCY_PROFILE`: profil latency antar region.

Menjalankan demo:

```bash
docker compose up --build
```

Lakukan update cache di leader:

```powershell
curl.exe -X POST http://localhost:8001/cache/set -H "Content-Type: application/json" -d '{\"key\":\"geo:key\",\"value\":{\"region\":\"asia\"},\"node_id\":\"node1\"}'
```

Cek propagasi ke follower:

```powershell
curl.exe -X GET http://localhost:8002/cache/status
curl.exe -X GET http://localhost:8003/cache/status
```

Poin presentasi yang bisa ditekankan:

1. Node dapat disimulasikan berada di beberapa region.
2. Jalur replikasi mengikuti profil latency.
3. Data menjadi konsisten pada akhirnya (eventual consistency).

## API Endpoints

### Distributed Lock Manager

#### Acquire Lock (`acquire`)
```powershell
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"file1\",\"node_id\":\"node1\"}'
```

Contoh respons sukses:
```json
{
  "status": "ok",
  "action": "acquire",
  "resource": "file1",
  "owner": "node1",
  "leader_id": "node2",
  "term": 1,
  "state": "leader"
}
```

#### Release Lock (`release`)
```powershell
curl.exe -X POST http://localhost:8001/lock/release -H "Content-Type: application/json" -d '{\"resource\":\"file1\",\"node_id\":\"node1\"}'
```

#### Check Lock Status
```powershell
curl.exe -X GET http://localhost:8001/lock/status
```

### Distributed Queue System

#### Enqueue Item (`enqueue`)
```powershell
curl.exe -X POST http://localhost:8002/queue/enqueue -H "Content-Type: application/json" -d '{\"item\":\"job-1\",\"node_id\":\"node1\"}'
```

Contoh respons:
```json
{
  "status": "ok",
  "action": "enqueue",
  "item": "job-1",
  "requested_by": "node1",
  "queue_size": 1,
  "leader_id": "node2",
  "term": 1,
  "state": "leader"
}
```

#### Dequeue Item (`dequeue`)
```powershell
curl.exe -X POST http://localhost:8002/queue/dequeue -H "Content-Type: application/json" -d '{\"node_id\":\"node1\"}'
```

#### Check Queue Status
```powershell
curl.exe -X GET http://localhost:8002/queue/status
```

### Cache Coherence

#### Set Cache Value (`set`)
```powershell
curl.exe -X POST http://localhost:8001/cache/set -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"value\":{\"name\":\"naufal\"},\"node_id\":\"node1\"}'
```

Contoh respons:
```json
{
  "status": "ok",
  "action": "set",
  "key": "user:1",
  "value": {"name": "naufal"},
  "version": 1,
  "updated_by": "node1",
  "leader_id": "node2",
  "term": 1,
  "state": "leader"
}
```

#### Get Cache Value (`get`)
```powershell
curl.exe -X GET "http://localhost:8001/cache/get?key=user:1"
```

#### Delete Cache Value (`delete`)
```powershell
curl.exe -X POST http://localhost:8001/cache/delete -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"node_id\":\"node1\"}'
```

#### Check Cache Status
```powershell
curl.exe -X GET http://localhost:8001/cache/status
```

## Important Notes

### PowerShell Command Format

Untuk `curl` di PowerShell, gunakan format dengan tanda kutip yang di-escape:

```powershell
curl.exe -X POST http://localhost:PORT/endpoint -H "Content-Type: application/json" -d '{\"key\":\"value\"}'
```

### Follower Forwarding

Jika request write dikirim ke follower, node follower akan meneruskan request ke leader secara otomatis.

```powershell
# Request is sent to node1 (follower)
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"file1\",\"node_id\":\"node1\"}'

# Follower forwards the request to the active leader
```

### Raft State in Responses

Setiap respons menyertakan kondisi cluster saat itu:

- `leader_id`: ID leader aktif.
- `term`: term Raft saat ini.
- `state`: peran node yang melayani request (`leader`, `follower`, atau `candidate`).

Penjelasan tambahan:
- Jika `state` bernilai `follower`, operasi tulis biasanya akan diteruskan ke leader.
- Jika `leader_id` kosong, cluster masih dalam proses pemilihan leader.

## Testing

Menjalankan unit test:

```bash
python -m unittest discover -s tests/unit -p "test_*.py"
```

Menjalankan benchmark lokal:

```bash
python benchmarks/load_test_scenarios.py
```

## Documentation

OpenAPI tersedia di `/openapi.json`, dan Swagger UI tersedia di `/docs`.

Dokumentasi tambahan:
- [Ikhtisar Arsitektur](docs/architecture.md)
- [Panduan Penerapan](docs/deployment_guide.md)
- [Laporan Performa](docs/performance_report.md)
- [Ringkasan Cakupan Rubrik](docs/rubric_coverage.md)

## Architecture Summary

```text
Node (leader)
|- Konsensus Raft
|  |- Pemilihan leader
|  |- Heartbeat
|  `- Manajemen vote
|- Lock Manager
|  |- acquire_lock
|  |- release_lock
|  `- list_locks
|- Queue Manager
|  |- enqueue
|  |- dequeue
|  `- list_queue
|- Cache Manager
|  |- set
|  |- get
|  |- delete
|  `- list_cache
`- Server HTTP
   |- /message (protokol Raft)
   |- /lock/* (endpoint lock)
   |- /queue/* (endpoint queue)
   |- /cache/* (endpoint cache)
   |- /openapi.json (spesifikasi OpenAPI)
   |- /docs (Swagger UI)
   `- /health (health check)
```

## Development

Struktur proyek:

```text
src/
|- consensus/
|  `- raft.py          # implementasi konsensus Raft
|- nodes/
|  |- base_node.py     # server HTTP node dan penanganan request
|  |- cache_manager.py # implementasi cache terdistribusi
|  |- lock_manager.py  # implementasi lock terdistribusi
|  `- queue_manager.py # implementasi queue terdistribusi
`- communication/
   `- message_passing.py
docs/
|- architecture.md
|- api_spec.yaml
`- deployment_guide.md
tests/unit/
|- test_lock_manager.py
|- test_queue_manager.py
`- test_cache_manager.py
main.py                  # titik masuk aplikasi
```

Catatan runtime:
- Folder `data/` dibuat otomatis saat persistence queue dijalankan.



