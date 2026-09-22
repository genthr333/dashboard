# Backend agregasi

Python 3.13, tanpa dependency eksternal. Mode default `simulation` (data fixture, tanpa koneksi); mode `production` (`DATA_MODE=production`) terhubung ke sumber nyata via `production.py`.

Dari folder `backend/`:

```sh
python3 server.py
```

Dashboard: http://127.0.0.1:8766/

## Endpoint

| Endpoint GET | Fungsi |
|---|---|
| `/healthz` | Kesehatan proses, bukan kesehatan upstream |
| `/api/v1/overview` | Respons agregasi 4 sumber |

Mode simulasi mendukung `?fail=<source>` dan `?stale=<source>` untuk testing UI; **ditolak (400) di mode produksi**.

## Environment variable (mode produksi)

Wajib:
- `DATA_MODE=production`
- `PRODUCTION_CONFIG` — path absolut ke `production.local.json`
- `SIGNOZ_URL`, `SIGNOZ_API_KEY`
- `PROMETHEUS_URL`, `PROMETHEUS_BEARER_TOKEN` (untuk Kuma, lihat PRODUCTION.md)
- `MATOMO_URL`, `MATOMO_TOKEN_AUTH`

Opsional:
- `HOST` (default `127.0.0.1`, Docker: `0.0.0.0`)
- `PORT` (default `8766`)

**PENTING**: semua koneksi ke sumber data WAJIB HTTPS (`production.py` menolak endpoint HTTP dengan `ConfigurationError`). Kalau sumber data self-hosted belum HTTPS, perlu reverse proxy TLS di depannya terlebih dulu.

## Status/RAG per aplikasi

Status (merah/kuning/hijau) dihitung dari kondisi **saat ini** (`up` dari Kuma), bukan rata-rata historis — mengikuti praktik umum status page (status terkini dan availability historis ditampilkan terpisah, tidak dicampur jadi satu angka).

```python
if not up or p95 >= 2000 or error_rate >= 0.05:
    status = "merah"
elif p95 >= 1500 or error_rate >= 0.02:
    status = "kuning"
else:
    status = "hijau"
```

Kolom "Uptime" di tabel tetap menampilkan rata-rata historis (default: 30 hari, diatur lewat `uptimeMtdQuery` di `production.local.json`) — untuk konteks SLA, bukan penentu warna status.

## Insiden

Dihasilkan otomatis dari aplikasi berstatus merah (bukan dari API insiden manapun, karena tidak ada satu pun sumber kita yang punya konsep "insiden" bawaan). 1 aplikasi merah = 1 entri insiden.

## Pengujian manual

Cek response API langsung:
```sh
curl http://127.0.0.1:8766/api/v1/overview
```