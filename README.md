# Observatory — Executive Observability

Dashboard eksekutif yang menggabungkan data dari SigNoz, Uptime Kuma, dan Matomo (Superset belum terhubung) ke satu tampilan. Mendukung mode simulasi (default, tanpa koneksi apa pun) dan mode produksi (`DATA_MODE=production`, terhubung ke sumber nyata).

## Jalankan (mode produksi)

Dari folder proyek, set environment variable berikut (lihat [PRODUCTION.md](PRODUCTION.md) untuk detail lengkap tiap sumber), lalu:

```sh
export DATA_MODE=production
export PRODUCTION_CONFIG="$(pwd)/backend/production.local.json"
# ...env var lain sesuai PRODUCTION.md
cd backend
python3 server.py
```

Buka http://127.0.0.1:8766/.

## Jalankan (Docker, direkomendasikan)

```sh
docker compose -f deploy/compose.yaml -f deploy/compose.production.yaml up --build
```

Buka http://localhost:8080. Nginx meneruskan API ke service `aggregator`. Sudah diuji jalan (Windows + Docker Desktop, 22 September 2026).

**Catatan penting**: sertifikat internal (`prometheus-ca.crt`) sudah "dibakar" ke dalam image lewat `Dockerfile` (`update-ca-certificates`), jadi tidak perlu dipasang manual di komputer masing-masing seperti sebelumnya.

## Isi paket

- `backend/server.py`: agregasi 4 sumber, endpoint GET `/api/v1/overview`, server HTTP (routing statis + API).
- `backend/production.py`: adapter yang menghubungkan ke SigNoz, Kuma (via Prometheus), Matomo, dan Superset di mode produksi.
- `backend/production.local.json`: konfigurasi query per sumber (rahasia/kredensial via environment variable, bukan file ini).
- `backend/README.md`: kontrak API, cara menjalankan, environment variable yang dibutuhkan.
- `dist/`: frontend yang membaca API setiap 60 detik.
- `deploy/`: Docker Compose (dasar + override produksi) dan konfigurasi Nginx.
- `PRODUCTION.md`: panduan lengkap menghubungkan tiap sumber data.

## Yang sudah berfungsi di mode produksi (per 22 September 2026)

- Status per-aplikasi (Kondisi/real-time, Status/gabungan, Uptime historis 30 hari, p95, error rate, request count) — dari SigNoz + Kuma.
- Grafik tren 24 jam (response time p95 + error rate) — dari SigNoz.
- Insiden aktif — otomatis muncul untuk aplikasi berstatus Kritis (merah).
- Analytics pengunjung — dari Matomo.
- Threshold status: Merah jika down, p95 ≥ 2000ms, atau error rate ≥ 5%. Kuning jika p95 ≥ 1500ms atau error rate ≥ 2%.

## Belum tersedia

- Superset (Kinerja bisnis) — belum dikonfigurasi.
- Global p95 gabungan lintas aplikasi — perlu ditambah query per sumber baru saat ada aplikasi kedua.