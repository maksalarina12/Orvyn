# Model Catalog — Orvyn

> Status: katalog belum bisa menginstal model otomatis — unduhan hanya dijalankan setelah konfirmasi user. `models/` masih kosong (fallback lokal belum aktif). Provider Space berikut sudah DIUJI nyata.

## Provider Space (terverifikasi)

| Space | Model | Tugas | Lisensi | Komersial | Cakupan | Status |
|---|---|---|---|---|---|---|
| `black-forest-labs/FLUX.1-schnell` | FLUX.1-schnell (ZeroGPU) | text-to-image 512–1024, 2–4 steps | Apache-2.0 (bobot model) | Diizinkan | dyZeroGPU kuota per-akun (anonim: sangat terbatas, terverifikasi cepat habis) | **TERVERIFIKASI nyata: generate berhasilsatu kali** |
| `stabilityai/stable-diffusion-3.5-large-turbo` | SD3.5 Large Turbo (ZeroGPU) | text-to-image + negative prompt | Stability community (bebas hingga pendapatan <$1 jt) | Terbatas | kuota ZeroGPU | dicatat, belum diuji end-to-end |

## Model lokal rancangan (belum terpasang)

| Model | Tugas | Lisensi | Komersial | Ukuran | Kebutuhan HW | Backend | Status |
|---|---|---|---|---|---|---|---|
| Stable Diffusion 1.5 (variants OpenRAIL-M) | text-to-image, inpainting | CreativeML OpenRAIL-M | Diizinkan dgn batasan | ±2,1 GB fp16 | CPU-only: estimasi 2–6 menit/512px | diffusers CPU (rancangan) | **not installed** |
| DreamShaper 8 | text-to-image (SD1.5-based) | CreativeML OpenRAIL-M | Diizinkan dgn batasan | ±2,1 GB | sama | sama | **not installed** |
| Realistic Vision (SD1.5-based) | text-to-image fotoreal | CreativeML OpenRAIL-M | Diizinkan dgn batasan | ±2 GB | sama | sama | **not installed** |

Catatan integritas:
- Repo asli SD1.5 (`runwayml/...`) sudah tidak tersedia di HF; pakai mirror/varian OpenRAIL-M dan **verifikasi lisensi + file hash saat mengunduh**.
- Model SDXL/Flux-Dev/video-generatif: **tidak layak untuk hardware ini** — jangan diunduh.
- Support negative_prompt/guidance tergantung Space (FLUX.1-schnell TIDAK punya kolom keduanya) — UI menampilkan limitation.
