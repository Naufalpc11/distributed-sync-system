# Distributed Sync System

Implementasi sistem sinkronisasi terdistribusi menggunakan Python (`asyncio`) sebagai bagian dari tugas Sistem Paralel dan Terdistribusi.

## Project Initialization

Langkah inisialisasi yang sudah dilakukan:

### 1. Create Repository

- Repositori dibuat dengan nama `distributed-sync-system`.
- Struktur folder mengikuti kebutuhan tugas.

### 2. Setup Virtual Environment (Required)

Buat virtual environment untuk isolasi dependency:

```bash
python -m venv .venv
```

Aktivasi di Windows PowerShell:

```bash
.\.venv\Scripts\activate
```

Jika berhasil, prompt terminal akan menampilkan prefix `(.venv)`.

### 3. Initial Dependency Installation

Library awal untuk komunikasi antar node:

```bash
pip install aiohttp
```

### 4. Generate `requirements.txt`

Simpan daftar dependency saat ini:

```bash
pip freeze > requirements.txt
```

### 5. Environment Validation

Pastikan interpreter Python berasal dari virtual environment:

```bash
python -c "import sys; print(sys.executable)"
```

Output seharusnya mengarah ke path seperti:

```text
...\.venv\Scripts\python.exe
```

## Project Structure

```text
distributed-sync-system/
|- src/
|- tests/
|- docker/
|- docs/
|- benchmarks/
|- requirements.txt
|- .env.example
|- README.md
`- main.py
```

## Current Progress

- Repositori dan struktur proyek sudah dibuat.
- Virtual environment sudah aktif.
- Dependency awal (`aiohttp`) sudah terpasang.
- Komunikasi dasar antar node melalui HTTP sudah siap.

## Next Steps

- Implementasi message passing antar node.
- Implementasi Raft (leader election).
- Implementasi Distributed Lock Manager.
- Implementasi Distributed Queue System.
- Implementasi Cache Coherence.

## Important Notes

- Selalu aktifkan `.venv` sebelum menjalankan proyek.
- Hindari instalasi package di global environment.
- Perbarui `requirements.txt` setiap ada dependency baru.

## Document Notes

File ini berfungsi sebagai catatan inisialisasi awal proyek. Untuk alur eksekusi terbaru, endpoint, dan deployment, gunakan `README.md` serta dokumen di folder `docs/`.

## Author

- Nama: [Isi Nama Kamu]
- NIM: [Isi NIM]



