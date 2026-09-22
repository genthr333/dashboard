# Menghubungkan data produksi

Mode produksi sudah ditambahkan, tetapi belum terhubung/diuji pada server Anda. URL, versi, hak akses dan mapping belum diberikan. Preview yang sedang berjalan tetap simulasi hingga backend direstart dengan konfigurasi produksi. Tidak ada fallback ke fixture dalam mode produksi.

## 1. Siapkan akses jaringan dan identitas

Jalankan backend dalam jaringan/VPN yang bisa mengakses keempat sumber. Pakai akun read-only, HTTPS dan CA internal tepercaya. Kredensial hanya pada environment server; jangan kirim di chat atau masukkan ke dist/config.js. Backend tidak menyediakan login: lindungi Nginx dan API dengan gateway SSO sebelum diakses melalui jaringan. Binding portal Docker tetap localhost:8080.

## 2. Konfigurasi lokal

Dari direktori proyek:

```sh
cp backend/production.example.json backend/production.local.json
cp deploy/.env.production.example deploy/.env.production
```

Isi secret di `.env.production` memakai editor/secret manager server. Kedua file lokal diabaikan Git. `production.local.json` memuat daftar aplikasi asli serta query tanpa secret. Ubah `enabled` ke true hanya untuk sumber yang selesai dikonfigurasi. Sumber lainnya akan tampil `not_configured`; tidak perlu menghubungkan semuanya sekaligus.

## 3. Matomo — koneksi pertama yang sederhana

Isi MATOMO_URL dan MATOMO_TOKEN_AUTH read-only. Atur `matomo.siteId` dan `matomo.enabled=true`. Backend POST `VisitsSummary.get` dan `Actions.get`, periode hari ini menurut timezone website Matomo, dengan token dalam body. Unique visitors mungkin null jika metrik tidak tersedia. Kunjungan nol menghasilkan bounce/durasi null, bukan angka palsu. Grafik per jam belum diimplementasikan untuk produksi.

## 4. Kuma — status dari Prometheus

Scrape `/metrics` Kuma menggunakan kredensial metrics sesuai versi. Kuma API key bukan API key CRUD/insiden umum. Atur PROMETHEUS_URL (HTTPS reverse proxy bila perlu), token bila endpoint memerlukannya, lalu query yang memilih **tepat satu seri monitor** per aplikasi, misalnya:

```json
{"currentStatusQuery":"monitor_status{monitor_name=\"Portal Production\"}","uptimeMtdQuery":null}
```

Ganti monitor name menggunakan label aktual. Nilai 0=down, 1=up; status lain unknown. `uptimeMtdQuery` harus menghasilkan satu rasio 0–1 dari recording rule/histori yang telah divalidasi. Jangan memakai rata-rata 30 hari sebagai SLA bulan berjalan. Query harus menangani data hilang, maintenance dan coverage; jika belum tersedia, biarkan null. RAG tetap unknown bila indikator wajib belum lengkap.

## 5. SigNoz — query sesuai metrik Anda

Isi SIGNOZ_URL dan SIGNOZ_API_KEY. Header yang dipakai `SIGNOZ-API-KEY`, endpoint POST `/api/v5/query_range`. Ambil payload query dari panel dashboard/Query Builder yang sudah benar pada versi Anda (browser Developer Tools → Network; jangan menyalin token). Untuk setiap aplikasi, isi p95Ms, requestCount dan errorCount dengan spesifikasi:

```json
{
  "body": {"start":"$START_MS","end":"$END_MS","requestType":"scalar","compositeQuery":{"queries":[]}},
  "valuePointer":"/REPLACE_WITH_ACTUAL_RESPONSE_PATH",
  "scale":1
}
```

Ini bentuk konfigurasi, **bukan query siap pakai**: ganti body, requestType dan queries dengan request valid dari instalasi Anda. valuePointer adalah JSON Pointer RFC 6901 yang memilih satu angka pada respons aktual, misalnya pola `/data/.../0/value` hanya jika sesuai schema yang diamati. Placeholder waktu diganti epoch ms 24 jam terakhir.

Request/error harus merupakan **jumlah 24 jam**, bukan request per detik. p95 harus kuantil 24 jam dalam milidetik (scale=1000 jika hasil detik). `globalP95Ms` menggunakan query histogram global untuk scope aplikasi yang sama; jangan merata-ratakan p95 aplikasi. Insiden dan trend produksi belum memiliki mapper, sehingga null. Tidak ada insiden demo yang dipindahkan ke produksi.

## 6. Superset — query KPI

# Menghubungkan data produksi

Mode produksi sudah terhubung dan teruji untuk SigNoz, Kuma (via Prometheus), dan Matomo. Superset belum dikonfigurasi.

## 1. Siapkan akses jaringan dan identitas

Jalankan backend dalam jaringan/VPN yang bisa mengakses sumber data. Pakai akun read-only, HTTPS, dan CA internal tepercaya.

**Semua koneksi WAJIB HTTPS** — `production.py` menolak endpoint HTTP (`ConfigurationError: HTTPS origin required`). Kalau server sumber (mis. Prometheus internal) belum HTTPS, perlu reverse proxy TLS (Nginx + certificate, self-signed juga bisa) di depannya dulu.

Kredensial hanya via environment variable di server; jangan taruh di `dist/config.js` atau file yang di-commit ke Git.

## 2. Konfigurasi lokal

Dari direktori proyek:

```sh
cp backend/production.example.json backend/production.local.json
```

Isi `production.local.json` dengan daftar aplikasi dan query per sumber (lihat contoh di bawah). File ini **tidak boleh** menyimpan secret/token — semua kredensial lewat environment variable.

## 3. Matomo

Env var: `MATOMO_URL`, `MATOMO_TOKEN_AUTH`.

```json
"matomo": { "enabled": true, "siteId": 4 }
```

Backend POST `VisitsSummary.get` dan `Actions.get` ke `MATOMO_URL/index.php`, periode hari ini. `siteId` didapat dari URL Matomo saat memilih situs (`idSite=X`).

## 4. Kuma (via Prometheus)

Kuma sendiri **tidak** menyediakan API query langsung yang cocok untuk backend ini — datanya perlu **discrape oleh Prometheus** terlebih dulu, baru di-query lewat PromQL.

**Setup infrastruktur (sekali saja):**
1. Deploy Prometheus, scrape config mengarah ke Kuma `/metrics` dengan `basic_auth` (username kosong, password = API Key dari Kuma Settings → Security → API Keys — **bukan** password login biasa, Basic Auth biasa akan gagal begitu API Key pertama dibuat).
2. Taruh reverse proxy TLS (Nginx) di depan Prometheus (lihat poin 1).

Env var: `PROMETHEUS_URL` (endpoint HTTPS Prometheus, bukan Kuma langsung), `PROMETHEUS_BEARER_TOKEN` (opsional, kalau proxy butuh auth tambahan).

```json
"kuma": {
  "enabled": true,
  "applications": {
    "portal": {
      "currentStatusQuery": "monitor_status{monitor_name=\"Nama Monitor Persis\"}",
      "uptimeMtdQuery": "avg_over_time(monitor_status{monitor_name=\"Nama Monitor Persis\"}[30d])"
    }
  }
}
```

`monitor_name` harus **persis** sama dengan label yang di-expose Kuma (cek lewat `curl` ke Prometheus `/api/v1/query?query=monitor_status`, hati-hati kalau ada monitor duplikat dengan nama sama tapi `monitor_url` beda — tambahkan filter `monitor_url` di query kalau terjadi).

`currentStatusQuery` menentukan status real-time (dipakai untuk warna status/RAG). `uptimeMtdQuery` untuk konteks historis di kolom Uptime tabel — **tidak** memengaruhi warna status. Window `[30d]` bisa diperpendek/perpanjang sesuai kebutuhan; makin pendek window, makin sensitif terhadap downtime sesaat.

## 5. SigNoz

Env var: `SIGNOZ_URL`, `SIGNOZ_API_KEY` (buat lewat Settings → Service Accounts → New Key, role Viewer cukup).

Endpoint: POST `/api/v5/query_range`, header `SIGNOZ-API-KEY`. Ambil payload query dari Query Builder (browser DevTools → Network, cari request `query_range`, copy body-nya).

**Per aplikasi**, isi 3 query (semua wajib, kalau salah satu `null` seluruh aplikasi tidak akan muncul di tabel):

```json
"portal": {
  "p95Ms": {
    "body": {"start":"$START_MS","end":"$END_MS","requestType":"scalar","compositeQuery":{"queries":[{"type":"builder_query","spec":{"name":"A","signal":"traces","aggregations":[{"expression":"p95(duration_nano)"}],"filter":{"expression":"service.name = 'NAMA_SERVICE'"}}}]}},
    "valuePointer": "/data/data/results/0/data/0/0",
    "scale": 0.000001
  },
  "requestCount": { "...": "sama, aggregations: count()" },
  "errorCount": { "...": "sama + filter tambahan: AND has_error = true" }
}
```

`globalP95Ms` (di level `signoz`, sejajar `applications`) — query p95 tanpa filter service, untuk panel ringkasan atas.

`trend` (di level `signoz`) — query **Time Series** (bukan scalar), 3 sub-query (p95, error count, total count) digabung jadi satu request untuk mengisi grafik 24 jam. Lihat `production.py` fungsi `signoz_trend()` untuk detail penggabungan.

Insiden dihasilkan otomatis dari aplikasi berstatus merah (lihat `server.py`), tidak butuh query terpisah.

## 6. Superset (belum diuji)

Isi `SUPERSET_URL` dan `SUPERSET_ACCESS_TOKEN` berupa access token service account read-only. Struktur sama seperti SigNoz.

## 7. Jalankan

**Docker (direkomendasikan):**
```sh
docker compose -f deploy/compose.yaml -f deploy/compose.production.yaml up --build
```
Buka http://localhost:8080. Certificate internal (kalau ada) harus dibakar ke image lewat `Dockerfile` (`update-ca-certificates`), bukan di-mount saat runtime — supaya tidak menimpa trust CA publik yang dibutuhkan Matomo.

**Manual (tanpa Docker):**
```sh
export DATA_MODE=production
export PRODUCTION_CONFIG="$(pwd)/backend/production.local.json"
# ...env var lain
cd backend && python3 server.py
```

Verifikasi: `curl http://localhost:8080/api/v1/overview`, cek `mode: production` dan status tiap source `ok`.

## Batas operasional

- Timeout per request ke sumber data: 8 detik. Timeout polling browser: 30 detik (dinaikkan dari default 10 detik — SigNoz query traces bisa butuh 10-15 detik).
- Nginx proxy_read_timeout: 60 detik (dinaikkan dari default 15 detik untuk alasan yang sama).
- Tidak ada retry otomatis, cache, atau refresh token otomatis.
- RAG/status: **merah** jika down ATAU p95≥2000ms ATAU error rate≥5%. **Kuning** jika p95≥1500ms ATAU error rate≥2%. Threshold ini disesuaikan untuk lingkungan internal/testing, bukan standar SLA publik — sesuaikan lagi sebelum dipakai untuk keputusan production sungguhan.

Referensi resmi: [SigNoz API](https://signoz.io/docs/metrics-management/query-range-api/), [Kuma Prometheus](https://github.com/louislam/uptime-kuma/wiki/Prometheus-Integration), [Matomo API](https://developer.matomo.org/guides/reporting-api).