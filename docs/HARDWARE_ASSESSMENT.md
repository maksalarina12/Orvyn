# Hardware Assessment — Orvyn

Ditulis saat audit awal (26 Okt 2026). Semua angka berasal dari perintah read-only yang benar-benar dijalankan, bukan perkiraan dokumen pabrikan. Estimasi kecepatan inference ditandai sebagai estimasi dan harus diverifikasi dengan generasi nyata pada Milestone 2.

## 1. Ringkasan sistem (hasil audit nyata)

| Item | Nilai terukur |
|---|---|
| OS | Ubuntu 26.04.1 LTS (Resolute Raccoon), x86_64 |
| CPU | Intel Core i5-8365U @ 1.60 GHz (WhiskeyLake-U, 4 core / 8 thread, TDP 15 W) |
| GPU | Intel UHD Graphics 620 (iGPU Gen9.5, GT2, 24 EU) — tidak ada driver NVIDIA, `nvidia-smi` tidak ada |
| RAM | 7,1 GiB total, ~4,3 GiB terpakai, ~2,7 GiB tersedia saat audit (buff/cache 2,6 GiB) |
| Swap | 4 GiB (hampir tidak terpakai saat audit) |
| Disk `/` | 233 GB, terpakai 159 GB, **bebas 63 GB** |
| Python | 3.13.13 (miniconda), pip 26.0.1 |
| Node.js / npm | v24.18.0 / 11.16.0 |
| Git | 2.53.0 |
| FFmpeg | 8.0.1-3ubuntu2 |
| Conda | tersedia (miniconda) |
| OpenCode | ada di `/home/laflame/.opencode/bin/opencode` |
| ComfyUI / model AI lokal | **tidak ditemukan** |
| Model / layanan inference lain | tidak ditemukan |

Kesimpulan audit: ini laptop low-power tanpa GPU diskrit. Profil inference-nya adalah CPU-only (atau iGPU via OpenVINO sebagai opsi eksperimental).

## 2. Apa yang bisa dijalankan secara realistis

### Image generation — FEASIBLE dengan batasan
Kelas model yang sesuai: **SD 1.5-class, resolusi 512 px, fp16, inference CPU**.

- Estimasi waktu (belum terverifikasi langsung): ±2–6 menit per gambar 512×512, 20–25 steps, 8 thread CPU. Harus diverifikasi saat Milestone 2.
- RAM inference: model fp16 ±2,1 GB di disk; saat berjalan butuh ±3–4 GB RAM bebas. Dengan RAM bebas ±2,7 GiB, wajib pakai flag low-memory (attention slicing, VAE slicing/tiled, fp16) dan antrian **concurrency = 1**.
- SDXL: **tidak praktis** (butuh ±6–8 GB RAM; akan thrashing swap).
- Flux dan model 2024+ besar: tidak disarankan.
- Opsi eksperimental di masa depan: OpenVINO di iGPU UHD 620 (Gen9.5 didukug CPU/iGPU OpenVINO). Ditunda sampai backend utama stabil.

### Video generatif — NOT FEASIBLE
Tidak ada CUDA, iGPU terlalu lemah, RAM 7 GiB tidak cukup untuk model text-to-video/image-to-video apa pun. Jangan dipasarkan. Yang berjalan nyata: **assembled/edited video via FFmpeg 8** (storyboard animatic, slideshow, title card, audio). Assemblase FFmpeg bukan AI video dan harus selalu diberi label “video assembly (FFmpeg)”.

### LLM lokal (untuk Guided Creation) — OPSIONAL, didefer
Fase 1 Guided Creation berjalan dengan template deterministik (tanpa LLM). LLM kecil (mis. Qwen3 0.6B via llama.cpp) bisa masuk Milestone terakhir bila RAM mengizinkan, tapi jadi prioritas rendah.

## 3. Kebutuhan disk & jaringan (terverifikasi vs estimasi)

| Kebutuhan | Ukuran | Sumber |
|---|---|---|
| PyTorch CPU wheel + deps | ±0,3–0,4 GB | download.pytorch.org (index CPU) — hindari CUDA wheel ±3 GB |
| diffusers, transformers, accelerate, safetensors | ±0,2–0,3 GB |
| Checkpoint SD 1.5 fp16 | ±2,1 GB | Hugging Face |
| venv + pip cache | ±0,7–1,2 GB |
| node_modules frontend | ±0,2–0,4 GB |
| Total awal | ±3,5–5 GB | Aman terhadap 63 GB bebas |

Unduh model **butuh konfirmasi user** (tetap kebijakan proyek).

## 4. Backend inference pertama yang direkomendasikan

**Keputusan**: backend adaptif lokal (`OrvynDiffusersBackend`) berbasis PyTorch CPU + Hugging Face diffusers, dijalankan sebagai worker subprocess terisolasi dengan antrian job.

Alasan (bukan preferensi):
1. Tanpa CUDA, ComfyUI hanya menambah kompleksitas (node graph) tanpa keuntungan performa pada CPU.
2. Adaptor terpisah tetap disiapkan: `backend/backends/` punya interface umum, sehingga adaptor ComfyUI/OpenVINO bisa masuk Milestone selanjutnya tanpa refactor.
3. Diffusers memberikan kontrol parameter (steps, guidance, seed, sampler) secara langsung dan tervalidasi.

## 5. Fitur yang harus ditunda

| Fitur | Status catatan |
|---|---|
| SDXL / Flux / video generatif | Ditunda — terlarang pada hardware ini |
| Multi-model paralel | Ditunda — antrian concurrency 1 |
| OpenVINO iGPU | Eksperimental, setelah backend utama jalan |
| LLM lokal untuk brief | Diterapkan template deterministik dulu |
| Inpainting | Bisa via SD 1.5 inpainting (±2 GB), dicatat di katalog — butuh konfirmasi download |
| Outpainting | Jangan dipromosikan sebelum terverifikasi |

## 6. Persetujuan user yang dibutuhkan sebelum install

1. `scripts/setup.sh` akan membuat **venv proyek** dan menginstal paket pip (tanpa sudo, reversible). Reversible → bisa lanjut tanpa tanya. ✔ diperbolehkan berjalan.
2. **Download checkpoint SD 1.5 fp16 (±2,1 GB)** dari Hugging Face → unduhan besar yang menghabiskan disk + kuota. Ini disebut di IMPLEMENTATION_PLAN sebagai gate yang butuh konfirmasi user.

## 7. Risiko terbesar

1. **RAM**: aplikasi browser (frontend) jalan bersamaan dengan worker inference dapat mendekati batas RAM bebas. Mitigasi: flag low-memory, antrian berserial, monitoring status di dashboard.
2. **Klaim tidak terverifikasi**: semua estimasi kecepatan di dokumen ini adalah estimasi; angka nyata dicatat di TEST_REPORT saat pertama kali generasi jalan.
