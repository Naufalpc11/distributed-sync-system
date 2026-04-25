# Distributed Sync System

Implementasi sistem sinkronisasi terdistribusi menggunakan Python (asyncio) sebagai bagian dari tugas Sistem Paralel dan Terdistribusi.

---

## 🚀 Setup Awal Project

Berikut langkah-langkah inisialisasi yang telah dilakukan:

### 1. Membuat Repository

* Repository dibuat dengan nama: `distributed-sync-system`
* Struktur folder mengikuti spesifikasi tugas

---

### 2. Setup Virtual Environment (WAJIB)

Membuat virtual environment untuk isolasi dependency:

```bash
python -m venv .venv
```

Aktivasi (Windows PowerShell):

```bash
.\.venv\Scripts\activate
```

Jika berhasil, terminal akan menampilkan:

```bash
(.venv)
```

---

### 3. Instalasi Dependency Awal

Menggunakan library utama untuk komunikasi antar node:

```bash
pip install aiohttp
```

---

### 4. Generate requirements.txt

Menyimpan semua dependency:

```bash
pip freeze > requirements.txt
```

---

### 5. Validasi Environment

Memastikan Python yang digunakan berasal dari virtual environment:

```bash
python -c "import sys; print(sys.executable)"
```

Output harus mengarah ke:

```
...\.venv\Scripts\python.exe
```

---

## 🧱 Struktur Project

```
distributed-sync-system/
├── src/
├── tests/
├── docker/
├── docs/
├── benchmarks/
├── requirements.txt
├── .env.example
├── README.md
└── main.py
```

---

## 🎯 Progress Saat Ini

✅ Repository & struktur project dibuat
✅ Virtual environment aktif
✅ Dependency awal (aiohttp) terinstall
✅ Sistem komunikasi antar node (basic HTTP) siap

---

## 🔜 Next Step

* Implementasi komunikasi antar node (message passing)
* Implementasi Raft (leader election)
* Distributed Lock Manager
* Distributed Queue System
* Cache Coherence

---

## ⚠️ Catatan Penting

* Selalu aktifkan `.venv` sebelum menjalankan project
* Jangan install package di global environment
* Update `requirements.txt` setiap menambah dependency

---

## 🧑‍💻 Author

* Nama: [Isi Nama Kamu]
* NIM: [Isi NIM]
