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

Isi SUPERSET_URL dan SUPERSET_ACCESS_TOKEN berupa access token service account read-only, **bukan guest token embed**. Adapter POST `/api/v1/chart/data`. Untuk tiap KPI, masukkan `body` query context dari chart resmi dan `valuePointer` ke nilai numerik respons. Bentuknya sama dengan spesifikasi SigNoz, tetapi body mengikuti Superset. Query KPI harus hari ini menurut Asia/Jakarta, unit rupiah, conversion ratio 0–1 (scale=0.01 jika API persen). Nilai yang tidak dipetakan null. Token yang kedaluwarsa menghasilkan error sumber; otomatis login/refresh token belum dibuat—rotasikan melalui secret manager dan restart.

## 7. Jalankan

```sh
docker compose -f deploy/compose.yaml -f deploy/compose.production.yaml up --build -d
```

Buka http://localhost:8080 dan http://localhost:8080/api/v1/overview. Verifikasi `mode=production`, status setiap source, serta angka dengan dashboard asli pada filter dan periode yang sama. `healthz` hanya memeriksa proses, bukan koneksi platform. Parameter fail/stale ditolak dalam produksi. Untuk menjalankan tanpa Docker, masukkan environment melalui process manager dan set PRODUCTION_CONFIG ke path absolut production.local.json, lalu `python3 backend/server.py`.

Setelah URL sumber tersedia, ganti tautan publik pada `dist/config.js`. Ini hanya mengubah drill-down; koneksi API diatur oleh backend.

## Batas operasional

Adapter melakukan read-only query, validasi angka/rasio, HTTPS verification, timeout tiap request 8 detik, batas respons 4 MiB dan pemblokiran redirect agar secret tidak dialihkan. Error sengaja tidak membocorkan body upstream atau token. Permintaan per aplikasi masih berurutan dalam satu adapter; lakukan batch query/cache sebelum scope besar. Polling browser saat ini timeout 10 detik sehingga query lambat dapat membuat UI menampilkan gagal; kurangi jumlah query/latensi sebelum rollout. Tidak ada cache/persistensi, retry atau token refresh otomatis. Ini fondasi integrasi, bukan klaim siap operasi produksi tanpa validasi.

`observedAt` saat ini adalah waktu siklus pengambilan, bukan timestamp event/refresh dataset. Matomo/Superset dapat mengembalikan hasil cache lama. Validasi timestamp data dari sumber sebelum menambahkan klaim fresh. SLA MTD, filter environment/service, KPI dan timezone wajib disepakati pemilik aplikasi. HTTP 200 atau source OK tidak otomatis berarti semua metrik lengkap.

Referensi resmi: [SigNoz API](https://signoz.io/docs/metrics-management/query-range-api/), [Kuma Prometheus](https://github.com/louislam/uptime-kuma/wiki/Prometheus-Integration), [Matomo API](https://developer.matomo.org/guides/reporting-api), [Superset API](https://superset.apache.org/developer-docs/api/).
