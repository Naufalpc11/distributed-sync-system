# Deployment Guide

## Local Development
1. Buat dan aktifkan virtual environment.
2. Install dependency dari `requirements.txt`.
3. Jalankan satu node per terminal, atau gunakan Docker Compose.
4. Buka `http://localhost:8001/docs` untuk melihat API.

### Quick Example
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py --id node1 --port 8001 --peers localhost:8002 localhost:8003
```

## Environment Variables
Gunakan `.env` atau flag CLI untuk konfigurasi berikut:
- `NODE_ID`
- `HOST`
- `ADVERTISE_HOST`
- `PORT`
- `PEERS`
- `REGION`
- `PEER_REGIONS`
- `LATENCY_PROFILE`

Penjelasan singkat:
- `ADVERTISE_HOST` dipakai node lain untuk menghubungi node ini.
- `PEERS` berisi daftar node lain dalam cluster.
- `LATENCY_PROFILE` dipakai saat simulasi multi-region.

Untuk menjalankan 3 node via file `.env` terpisah, pastikan setiap node memiliki `PORT` unik (misalnya `8001`, `8002`, `8003`). Jika `PORT` tidak diset, aplikasi fallback ke `8000` dan bisa menyebabkan bentrok port.

## Docker Deployment
Sebelum menjalankan Docker, pastikan tidak ada proses lokal lain yang memakai port `8001-8003`.

Jalankan seluruh stack:

```bash
docker compose up --build
```

Hentikan stack:

```bash
docker compose down
```

## Runtime Files
- Persistence queue disimpan sebagai file SQLite di folder `data/`.
- Folder `data/` akan dibuat otomatis saat aplikasi berjalan.

## Troubleshooting
- Jika follower mengembalikan `leader belum diketahui`, tunggu sampai pemilihan leader Raft stabil.
- Jika `curl` di PowerShell gagal, gunakan `curl.exe` (bukan alias `curl`).
- Jika node tidak bisa menjangkau peer, periksa `ADVERTISE_HOST`, `PORT`, dan konfigurasi jaringan Docker/.env.
- Jika data queue terlihat tidak sinkron, cek apakah leader berubah atau node restart dengan file SQLite baru.
- Jika endpoint tidak merespons setelah startup, lihat log node dan pastikan tidak ada bentrok port.
