> Mode produksi kini tersedia. Lihat [panduan produksi](../PRODUCTION.md). Koneksi aktual memerlukan konfigurasi server; petunjuk simulasi berikut tetap berlaku untuk mode default.

# Backend agregasi simulasi

Python 3.10+ tanpa dependency eksternal. Empat adapter mengembalikan struktur normalisasi internal, **bukan tiruan persis response API vendor**. Tidak membutuhkan token/internet. Mode default tetap simulation; produksi harus dipilih eksplisit melalui DATA_MODE=production.

Dari folder proyek:

```sh
python3 backend/server.py
```

Dashboard: http://127.0.0.1:8766/

| Endpoint GET | Fungsi |
|---|---|
| `/healthz` | Kesehatan proses, bukan kesehatan upstream |
| `/api/v1/overview` | Respons agregasi empat adapter |
| `/api/v1/overview?fail=signoz` | Simulasi sumber gagal |
| `/api/v1/overview?stale=matomo` | Simulasi data sumber berumur satu jam |
| `/api/v1/overview?fail=kuma&stale=superset` | Skenario gabungan |

Nilai fail/stale: `signoz`, `kuma`, `matomo`, `superset`. Query tidak dikenal, kosong atau berulang → 400. Endpoint tak dikenal → 404. POST → 405. Partial upstream → HTTP 200 dengan `status: partial`, metadata sumber gagal/stale dan nilai null. Tidak ada fallback diam-diam ke angka sehat. fail mengalahkan stale bila sumber sama.

Respons mencakup `schemaVersion`, `mode`, `generatedAt`, `windows`, `sources`, `metrics`, `healthCounts`, `applications`, `incidents`, `performanceTrend`, `analytics`, `business`, dan `definitions`. Rasio menggunakan skala 0–1; waktu UTC ISO 8601; UI menampilkan WIB. Fixture tetap deterministik, timestamp digeser mengikuti waktu request. Trend adalah sampel titik per jam; error rate agregat dihitung dari jumlah request/error 24 jam dan bukan rerata titik trend.

Agregasi default: 8 aplikasi; 6 sehat, 1 waspada, 1 kritis; 1.280.000 request; 3.142 error; error rate 0,24546875%; health 75%. Angka error berbeda dari prototipe statis lama karena kini dihitung konsisten dari volume tiap aplikasi. p95 342 ms merupakan fixture kuantil global. Availability MTD berasal dari fixture riwayat monitor, bukan perhitungan riwayat yang disimpan oleh server ini.

`ThreadPoolExecutor` menjalankan adapter independen. Fixture tidak melakukan I/O sehingga tidak membutuhkan retry. Saat menambahkan HTTP vendor client, wajib tambahkan timeout transport, validasi schema, retry terbatas, secret server-side dan cache; pool saja tidak membatasi durasi panggilan yang macet. Endpoint belum memiliki auth dan hanya listen localhost secara default. Tempatkan di belakang gateway SSO sebelum akses jaringan.

Environment: `HOST=127.0.0.1`, `PORT=8766`, `DATA_MODE=simulation`. Compose menjalankan backend pada network container, Nginx meneruskan `/api/` dan mengekspos portal hanya localhost:8080. Service tidak membuka port backend langsung ke host. File `.env.example` lama adalah placeholder integrasi produksi, belum dibaca oleh adapter simulasi.

Untuk melihat kegagalan di UI, sementara ubah `summaryEndpoint` di `dist/config.js` menjadi `/api/v1/overview?fail=signoz`. Segarkan dashboard. Kembalikan ke endpoint tanpa query untuk kondisi default. Polling UI 60 detik; kegagalan seluruh API membersihkan indikator agar data lama tidak terlihat sebagai status terkini.

Pengujian:

```sh
python3 -m unittest discover -s backend -v
```

`overview.example.json` adalah respons lengkap hasil generator backend. Angka siap dipakai pengembang frontend; tidak merepresentasikan kondisi produksi.
