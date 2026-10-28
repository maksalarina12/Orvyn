# Troubleshooting — Orvyn

- **Backend tidak membalas di 8187**: cek `logs/backend.log`; pastikan `.venv` sudah dibuat (`scripts/setup.sh`).
- **esbuild binary missing npm postinstall**: jalankan `cd frontend && npm approve-scripts esbuild rebuild` (npm 11 blokir postinstall script pada beberapa setup; binari risetnya dilink manual di milestone awal).
- **Frontend tidak start**: pastikan `frontend/node_modules` ada; jalankan development dengan `cd frontend && npm run dev`; log: `logs/frontend.log`.
- **Provider HF Space “unreachable”**: Space bisa sleep/berubah/dikuarota; cek URL + endpoint Gradio (`/gradio_api/call/{api_name}`); UI tidak akan menyamarkan `unreachable`.
- **Error “Space gagal memproses: null” (ZeroGPU)**: kuota GPU anonim habis (perilaku terverifikasi 26 Okt 2026). Solusi: daftar akun HF gratis → token `hf_...` → isi di Model & Backend (kartu provider, field token) atau set env `HF_TOKEN` sebelum start. Tanpa token dari satu IP, anonim hanya dapat alokasi sangat kecil.
- **Job `failed: name 'X' is not defined`** seusai edit kode: restart backend (`scripts/stop.sh && scripts/start.sh`).
- **RAM ketat saat generation lokal (masa depan)**: tutup browser berat, gunakan steps rendah 4–8, satu image per job.
- **Disk penuh**: `data/outputs/...` menumpuk — bersihkan manual, tidak ada auto-delete.
- **Port bentrok**: backend 8187 / frontend 5170 (diubah lewat env `ORVYN_PORT` dan `frontend/vite.config.ts`).
