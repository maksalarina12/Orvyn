# Installation & Operation — Orvyn

## Prasyarat
- Ubuntu (diuji: 26.04), Python 3.11+, Node 18+ (diuji: 24), FFmpeg, git.
- Tidak perlu NVIDIA. Inference CPU-friendly by design.

## Instalasi
```bash
scripts/check-system.sh   # audit read-only
scripts/setup.sh          # venv + pip + npm (tanpa sudo, tanpa unduhan model)
scripts/start.sh          # jalankan backend+frontend
```

- UI: http://127.0.0.1:5170
- API docs: http://127.0.0.1:8187/docs

## Menghentikan
```bash
scripts/stop.sh
```

## Data
Semua data pengguna di `data/` (SQLite `orvyn.db`, aset, output). Hapus folder = hapus data — tidak ada operasi penghapusan di setup/start.

## Aktivasi provider generation (opsional, setelah Step-1 shell jalan)
1. Buka **Model & Backend** di UI.
2. Untuk provider HF Space: isi Space URL + nama endpoint Gradio, klik Aktifkan → **konfirmasi sadar** (data terkirim ke pihak ketiga).
3. Untuk fallback lokal: unduhan model ±2,1 GB hanya dijalankan setelah konfirmasi (belum ditawarkan s/d gateway tervalidasi).

## Test
```bash
scripts/test.sh
```
