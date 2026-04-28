# Distributed Sync System

Implementasi sistem sinkronisasi terdistribusi menggunakan Python dengan Raft consensus dan distributed lock/queue management.

## Features
- Raft Leader Election
- Distributed Lock Manager
- Distributed Queue System
- Cache Coherence

## Quick Start

### 1. Setup Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 1b. Environment Template

File `.env.example` disediakan sebagai template konfigurasi proyek. Kalau nanti ingin memakai environment variable, cukup salin file itu menjadi `.env` lalu sesuaikan nilainya. Untuk demo saat ini, project tetap bisa dijalankan langsung dengan argumen CLI seperti di bawah.

### 2. Jalankan 3 Node

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

Tunggu hingga salah satu menampilkan `[nodeX] Became LEADER`.

### 3. Demo Manual End-to-End (Start to Finish)

Langkah ini bisa langsung dipakai saat presentasi:

1. Aktifkan virtual environment dan install dependency.
2. Jalankan 3 node di 3 terminal terpisah.
3. Tunggu hingga ada leader terpilih (`Became LEADER`).
4. Uji Lock:

```powershell
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"demo-lock\",\"node_id\":\"node1\"}'
curl.exe -X GET http://localhost:8003/lock/status
curl.exe -X POST http://localhost:8001/lock/release -H "Content-Type: application/json" -d '{\"resource\":\"demo-lock\",\"node_id\":\"node1\"}'
```

5. Uji Queue:

```powershell
curl.exe -X POST http://localhost:8002/queue/enqueue -H "Content-Type: application/json" -d '{\"item\":\"job-1\",\"node_id\":\"node1\"}'
curl.exe -X GET http://localhost:8001/queue/status
curl.exe -X POST http://localhost:8002/queue/dequeue -H "Content-Type: application/json" -d '{\"node_id\":\"node1\"}'
```

6. Uji Cache Coherence:

```powershell
curl.exe -X POST http://localhost:8001/cache/set -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"value\":{\"name\":\"naufal\"},\"node_id\":\"node1\"}'
curl.exe -X GET "http://localhost:8002/cache/get?key=user:1"
curl.exe -X GET http://localhost:8003/cache/status
curl.exe -X POST http://localhost:8001/cache/delete -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"node_id\":\"node1\"}'
```

7. Hentikan semua node dengan `Ctrl + C` di masing-masing terminal.

### 4. Jalankan dengan Docker

Kalau kamu mau demo tanpa buka 3 terminal Python manual, pakai Docker Compose:

```bash
docker compose up --build
```

Setelah container jalan, kamu bisa akses endpoint yang sama seperti demo manual. Contoh:

```powershell
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"docker-lock\",\"node_id\":\"node1\"}'
curl.exe -X POST http://localhost:8002/queue/enqueue -H "Content-Type: application/json" -d '{\"item\":\"docker-job\",\"node_id\":\"node1\"}'
curl.exe -X POST http://localhost:8001/cache/set -H "Content-Type: application/json" -d '{\"key\":\"docker:key\",\"value\":{\"active\":true},\"node_id\":\"node1\"}'
```

Kalau mau stop container:

```bash
docker compose down
```

---

## API Endpoints

### Distributed Lock Manager

#### Acquire Lock
```powershell
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"file1\",\"node_id\":\"node1\"}'
```

Response (jika berhasil):
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

#### Release Lock
```powershell
curl.exe -X POST http://localhost:8001/lock/release -H "Content-Type: application/json" -d '{\"resource\":\"file1\",\"node_id\":\"node1\"}'
```

#### Check Lock Status
```powershell
curl.exe -X GET http://localhost:8001/lock/status
```

---

### Distributed Queue System

#### Enqueue Item
```powershell
curl.exe -X POST http://localhost:8002/queue/enqueue -H "Content-Type: application/json" -d '{\"item\":\"job-1\",\"node_id\":\"node1\"}'
```

Response:
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

#### Dequeue Item
```powershell
curl.exe -X POST http://localhost:8002/queue/dequeue -H "Content-Type: application/json" -d '{\"node_id\":\"node1\"}'
```

#### Check Queue Status
```powershell
curl.exe -X GET http://localhost:8002/queue/status
```

---

### Cache Coherence

#### Set Cache Value
```powershell
curl.exe -X POST http://localhost:8001/cache/set -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"value\":{\"name\":\"naufal\"},\"node_id\":\"node1\"}'
```

Response:
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

#### Get Cache Value
```powershell
curl.exe -X GET "http://localhost:8001/cache/get?key=user:1"
```

#### Delete Cache Value
```powershell
curl.exe -X POST http://localhost:8001/cache/delete -H "Content-Type: application/json" -d '{\"key\":\"user:1\",\"node_id\":\"node1\"}'
```

#### Check Cache Status
```powershell
curl.exe -X GET http://localhost:8001/cache/status
```

---

## Important Notes

### PowerShell Command Format
Untuk curl di PowerShell, gunakan format dengan escaped quotes:
```powershell
curl.exe -X POST http://localhost:PORT/endpoint -H "Content-Type: application/json" -d '{\"key\":\"value\"}'
```

### Follower Forwarding
Jika kamu kirim request ke follower node, request akan otomatis diteruskan ke leader:
```powershell
# Ini ke node1 (follower)
curl.exe -X POST http://localhost:8001/lock/acquire -H "Content-Type: application/json" -d '{\"resource\":\"file1\",\"node_id\":\"node1\"}'

# Akan diteruskan ke leader otomatis
```

### Raft State
Setiap response mencakup state leader terkini:
- `leader_id`: ID leader yang aktif saat ini
- `term`: Term saat ini
- `state`: State node (leader/follower/candidate)

---

## Test

Jalankan unit test:
```bash
python -m unittest discover -s tests/unit -p "test_*.py"
```

---

## Architecture

```
Node (leader)
├── Raft Consensus
│   ├── Leader Election
│   ├── Heartbeat
│   └── Vote Management
├── Lock Manager
│   ├── acquire_lock
│   ├── release_lock
│   └── list_locks
├── Queue Manager
│   ├── enqueue
│   ├── dequeue
│   └── list_queue
├── Cache Manager
│   ├── set
│   ├── get
│   ├── delete
│   └── list_cache
└── HTTP Server
    ├── /message (Raft protocol)
    ├── /lock/* (Lock endpoints)
    ├── /queue/* (Queue endpoints)
    ├── /cache/* (Cache endpoints)
    └── /health (Health check)
```

---

## Development

Struktur project:
```
src/
├── consensus/
│   └── raft.py          # Raft consensus implementation
├── nodes/
│   ├── base_node.py     # Node HTTP server & request handling
│   ├── cache_manager.py # Distributed cache implementation
│   ├── lock_manager.py  # Distributed lock implementation
│   └── queue_manager.py # Distributed queue implementation
└── communication/
    └── message_passing.py
tests/unit/
├── test_lock_manager.py
├── test_queue_manager.py
└── test_cache_manager.py
main.py                  # Entry point
```