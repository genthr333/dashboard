> Mode produksi kini tersedia. Lihat [panduan produksi](PRODUCTION.md). Koneksi aktual memerlukan konfigurasi server; petunjuk simulasi berikut tetap berlaku untuk mode default.

# Observatory — Executive Observability

Dashboard kini mengambil data dari backend agregasi simulasi empat platform. Semua angka dan insiden masih simulasi; belum ada koneksi produksi.

## Jalankan

Dari folder proyek jalankan `python3 backend/server.py`, kemudian buka http://127.0.0.1:8766/. Jangan membuka HTML langsung atau memakai server statis lama pada port 8765 karena endpoint API tidak tersedia di sana.

Alternatif Docker: `docker compose -f deploy/compose.yaml up --build -d`, lalu buka http://localhost:8080. Nginx meneruskan API ke service aggregator. Docker belum diuji pada sesi ini.

## Isi paket

- `backend/server.py`: empat adapter simulasi, agregasi, endpoint GET `/api/v1/overview`, serta server frontend.
- `backend/README.md`: kontrak, contoh URL, failure/stale simulation, cara menjalankan dan batas implementasi.
- `backend/test_server.py`: pengujian perhitungan, isolasi kegagalan dan stale data.
- `dist/`: frontend yang membaca API setiap 60 detik; semua panel data utama memakai respons backend.
- `overview.example.json`: contoh respons lengkap.
- `deploy/`: Compose, Nginx dan Dashy opsional.
- `INTEGRATION.md`: rancangan koneksi ke platform produksi.

Status sumber API dapat OK meski aplikasi yang dipantau kritis; kedua hal tersebut berbeda. Endpoint dan dashboard diberi label simulasi. Data gagal/kedaluwarsa menjadi null/unknown. Tidak ada token diperlukan. Gunakan gateway SSO sebelum akses jaringan produksi.
