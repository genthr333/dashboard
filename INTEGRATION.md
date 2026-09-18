> Pembaruan: backend simulasi sekarang tersedia di `backend/server.py`; frontend sudah membaca `/api/v1/overview`. Compose menyertakan aggregator dan Nginx meneruskan `/api/`. Lihat `backend/README.md` untuk implementasi yang berjalan. Bagian berikut adalah rencana koneksi produksi, bukan fitur live yang sudah dibuat.

# Integrasi dan deployment

## Arsitektur yang disarankan

Browser/NOC → HTTPS ingress + OIDC/SSO → portal statis + BFF `/api/v1/overview` → adapter SigNoz, Prometheus/Kuma, Matomo, Superset.

Dashy dapat menjadi launchpad menuju portal dan sumber. Portal custom menangani agregasi executive, karena iframe saja tidak menyatukan data/semantik. Contoh Dashy di paket ini memakai tautan. Bila menginginkan iframe, tambahkan widget iframe sesuai versi Dashy yang dipin dan izinkan origin Dashy pada CSP portal; hindari nested iframe untuk semua platform sekaligus.

## Pemetaan endpoint

| Sumber | Endpoint placeholder / adapter | Indikator | Auth server |
|---|---|---|---|
| SigNoz | `https://signoz.example.org/api/v5/query_range` (POST) | histogram latency, error, request, alert melalui adapter terpisah | API key; ikuti header/role versi terpasang |
| Uptime Kuma | `https://kuma.example.org/metrics` di-scrape Prometheus | status monitor + heartbeat, riwayat availability dari TSDB | konfigurasi auth metrics sesuai versi Kuma |
| Matomo | `https://matomo.example.org/index.php` Reporting API, POST `module=API`, `method=VisitsSummary.get`, `idSite=1`, window, `format=JSON` | unique visitors, visits, bounce, duration; `Actions.get` untuk pageviews | token_auth read-only melalui body server-side |
| Superset | `/api/v1/chart/data` dengan query context chart yang telah disetujui | transaksi, nilai, conversion, target | service account / access token; sesuaikan versi |
| Superset embed | `/api/v1/security/guest_token/` dipanggil server | drill-down dashboard via Embedded SDK | short-lived guest token dibatasi dashboard + RLS |

Path bersifat contoh untuk versi yang sesuai; payload SigNoz/chart Superset perlu dibuat berdasarkan nama metric, service, dataset, dan schema aktual. Tidak ada universal payload yang dapat dipakai tanpa mapping. KPI unik tidak boleh diperoleh dengan menjumlahkan unique visitor per jam. Konversi perlu definisi numerator/denominator dan dataset bisnis yang sama.

Kuma `/metrics` bukan endpoint historis SLA dan bukan API insiden umum. Simpan scrape di Prometheus; definisikan periode maintenance, interval scrape, missing samples dan bobot waktu untuk menghitung availability. Jangan anggap sampel hilang berarti up. Korelasikan alert SigNoz dan transisi Kuma dengan kunci aplikasi + gejala; deduplikasi dan persist lifecycle insiden di backend. Owner, prioritas dan waktu mulai bukan field yang dijamin hadir di empat sumber.

## Kontrak BFF dan ketahanan

`overview.example.json` adalah kontrak awal yang diusulkan. Production renderer harus membaca endpoint ini dan memvalidasi schema. Ambil sumber paralel dengan timeout per sumber 5–10 detik; cache berdasarkan tenant/role/scope. Poll operasi 60 detik, Matomo 5 menit, bisnis 15 menit, backoff saat gagal dan hindari request bertumpuk. Interval ini pilihan rancangan, bukan janji freshness platform.

Setiap sumber dan metrik memiliki `observedAt`, `window`, `status`, dan `error`. Ambang stale contoh: operasi 180 detik, Matomo 15 menit, bisnis 45 menit. Gagal/hilang/stale ditampilkan abu-abu dengan umur data; data terakhir boleh terlihat tetapi ditandai stale. Jangan mengganti kegagalan dengan nol/hijau atau fixture demo. Beri label provisional bila periode belum lengkap. Setiap metrik harus melacak lineage sumber, unit, aggregation, dan denominator.

Untuk produksi, pisahkan status real-time dari kepatuhan SLA MTD agar pelanggaran historis tidak dikira gangguan aktif; aturan RAG contoh di prototipe sengaja mengangkat keduanya untuk perhatian manajemen. Tetapkan criticality weights dan SLO per aplikasi bersama owner.

## Auth dan akses

- Lindungi portal **dan BFF** dengan gateway OIDC dan pemeriksaan role server (`management`, `noc`). Network internal saja tidak menggantikan autentikasi.
- Cookie sesi Secure + HttpOnly; SameSite disesuaikan alur login; lindungi mutasi dengan CSRF. Hapus header identity dari klien sebelum gateway menetapkan identity terpercaya.
- Simpan token sumber pada secret manager/server environment. Jangan taruh token di JS, localStorage, HTML, query string iframe, log atau Git.
- Batasi service account read-only dan tenant/dataset. Tolak ID sumber/URL sewenang-wenang agar BFF tidak menjadi proxy terbuka/SSRF. Allowlist origin dan resource ID di server.
- Superset SDK menerima guest token singkat dari backend setelah validasi sesi dan hak dashboard; batasi resource dan row-level security. Service account access token tidak dikirim ke browser.

## Iframe, CSP, X-Frame-Options

CSP `frame-src` portal menentukan origin yang boleh dimuat; CSP `frame-ancestors` pada **respons sumber** menentukan siapa yang boleh membingkainya. Mengubah CSP portal saja tidak membuka izin sumber.

Gunakan allowlist origin exact, misalnya sumber mengizinkan `frame-ancestors 'self' https://monitor.example.org`. `X-Frame-Options: DENY` atau `SAMEORIGIN` dapat menolak embedding lintas origin; jangan menghapus header secara global. Atur kebijakan hanya pada route embed yang didukung, dengan koordinasi admin. `ALLOW-FROM` bukan solusi browser modern.

SigNoz/Kuma: gunakan link sebagai fallback bila embed tidak didukung atau tidak cocok untuk auth. Matomo: widget embed tersedia, tetapi token dalam URL terekspos ke browser; prototipe ini memilih agregasi Reporting API server-side. Superset: gunakan Embedded SDK, enabled embedding, allowed domains dan guest token berumur pendek. Sesuaikan CSP/Talisman melalui konfigurasi versi deployment.

Cookie lintas situs dapat diblokir meski `SameSite=None; Secure`; SSO tidak otomatis membuat semua iframe login. Jangan proxy halaman login sembarangan atau menonaktifkan proteksi browser. Sediakan tombol membuka sumber di tab baru sebagai fallback. Uji CSP report-only sebelum menerapkan kebijakan produksi; konfigurasi Nginx contoh menggunakan inline style untuk grafik, bukan inline script.

## Deployment

Compose melayani frontend dan **backend simulasi**. Endpoint `/api/v1/overview` kini mengembalikan hasil agregasi simulasi. Setelah BFF dibangun, ubah lokasi ini menjadi proxy ke service agregator, tambahkan service/image yang benar-benar tersedia, auth middleware, TLS ingress, healthcheck, logging tanpa token dan secret injection. File `.env.example` adalah daftar kebutuhan, belum dikonsumsi aplikasi.

NOC: gunakan perangkat terkelola, akun hanya-baca, resolusi ideal 1920×1080, browser zoom 100%, layar penuh. Uji refresh token, outage sumber, partial data, timezone Asia/Jakarta, perubahan hari/bulan, isolation role, dan konflik CSP sebelum rollout.

## Referensi resmi

- SigNoz Metrics API: https://signoz.io/docs/metrics-management/query-range-api/
- Kuma Prometheus: https://github.com/louislam/uptime-kuma/wiki/Prometheus-Integration
- Matomo Reporting API: https://developer.matomo.org/api-reference/reporting-api
- Matomo auth: https://developer.matomo.org/guides/authentication-in-depth
- Superset embedding: https://superset.apache.org/user-docs/using-superset/embedding/
- Superset networking: https://superset.apache.org/docs/configuration/networking-settings/
- Dashy widgets: https://dashy.to/docs/widgets/
