# Observatory — Executive Observability

Prototipe satu halaman untuk manajemen/NOC, berbahasa Indonesia, tema gelap, tanpa dependency frontend. Semua angka, insiden, tren, dan owner adalah **data simulasi**. Tidak ada koneksi produksi, polling API, autentikasi aplikasi, atau adapter sumber yang sudah aktif. Jam header adalah jam saat ini; snapshot data tetap 16 September 2026 14:32 WIB.

## Jalankan dan sesuaikan

Buka `dist/index.html` langsung pada browser; atau jalankan `docker compose -f deploy/compose.yaml up -d` lalu buka http://localhost:8080. Profil opsional Dashy: `docker compose -f deploy/compose.yaml --profile dashy up -d` (localhost:8081). Compose mengikat port ke localhost; akses jaringan membutuhkan reverse proxy TLS dan gateway SSO.

- `dist/config.js`: empat domain placeholder, path dashboard dan kontrak endpoint agregasi. Tidak boleh menyimpan secret.
- `dist/app.js`: fixture aplikasi, metrik, aturan tampilan, grafik dan interaksi.
- `dist/style.css`: layout desktop 1920×1080 / 1440×900, serta fallback mobile.
- `deploy/`: Compose, Nginx, launchpad Dashy, dan contoh variabel server.
- `INTEGRATION.md`: pemetaan sumber, auth, embedding, data freshness, serta langkah produksi.
- `overview.example.json`: contoh kontrak API yang diusulkan, bukan response API platform asli.

Fungsi yang tersedia: filter semua/perlu perhatian, detail tiap aplikasi, ringkasan insiden, drill-down sumber, definisi indikator, mode layar penuh. Tidak ada tombol yang melakukan acknowledge/resolve insiden. Tautan sumber belum dipetakan ke aplikasi individual: ganti dengan dashboardId/serviceName/monitorId/siteId per aplikasi.

## Layout

Health banner → lima indikator operasional → tren latency/error + insiden → delapan aplikasi RAG + Matomo/Superset → empat dashboard sumber. Status tetap memiliki label teks agar tidak bergantung pada warna. Tidak ada iframe aktif pada halaman utama sehingga dashboard tetap ringkas dan tidak tergantung sesi empat platform.

## Aturan contoh

- Health = aplikasi hijau / seluruh aplikasi dalam scope; tampilkan gray/unknown terpisah bila data tidak tersedia.
- Hijau: uptime MTD ≥99,90%, p95 <500 ms, error <0,50%.
- Merah: monitor down, uptime MTD <99,90%, p95 ≥1.000 ms, atau error ≥2%.
- Kuning: kondisi di antara ambang di atas; pilih status terburuk.
- Availability overview = rerata uptime aplikasi berbobot sama, 99,95% setelah pembulatan. Ini tidak menggantikan penilaian SLA per aplikasi: Payment Gateway melanggar.
- p95 global berasal dari distribusi seluruh request, bukan rata-rata p95 aplikasi. Error global = total HTTP 5xx / total request.
- Operasional/tren: trailing 24 jam; uptime/SLA: bulan berjalan. Matomo: 24 jam; Superset: hari ini, dibandingkan hari sebelumnya pada jam sama. Tetapkan window yang konsisten saat implementasi.

## Batas dan langkah berikut

Prototipe siap sebagai dasar pengembangan, **bukan sistem produksi siap pakai**. Implementasikan BFF yang diautentikasi, adapter empat sumber, model data, pemetaan aplikasi, freshness/unknown handling dan audit akses sebelum mengganti data contoh. Jangan sekadar mengganti `mode` menjadi live: renderer saat ini selalu membaca fixture. Digest image dan aturan SLA perlu diputuskan tim operasional.
