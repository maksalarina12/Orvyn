# Cost & Licenses — Orvyn

## 1. Kebijakan free-first (diperbarui 26 Okt 2026)

- Tidak ada API berbayar di jalur utama. Tidak ada kunci API yang dibutuhkan untuk core local generation.
- Komputasi gratis berkuota diizinkan sebagai **provider opsional** (Hugging Face ZeroGPU Spaces, Gradio API):
  - Kuota akun gratis ±5 menit GPU/hari (≈10–30 gambar SD-class). Bukan "gratis tanpa batas" — UI menampilkan status provider dan penyebab gagal secara jujur.
  - Kuota dan ketersediaan Space dapat berubah tanpa pemberituan; tidak dijadikan satu-satunya jalur generasi.
  - **Disabled by default.** Mengirim prompt/aset ke Space = mengirim data ke pihak ketiga; butuh persetujuan eksplisit user sebelum pengiriman pertama. Institusi file/pendapat pribadi tidak pernah dikirim otomatis.
- **Pollinations.ai (API Classic) — provider opsional kedua (ditambahkan 27 Okt):**
  - Gratis tanpa kunci, rate-limited; model default saat verifikasi: "sana" (bisa berubah tanpa pemberituan).
  - Mode: text-to-image saja (model image-to-image "kontext" butuh kunci berbayar — tidak dipakai).
  - **Disabled by default**, butuh konfirmasi eksternal; mengirim prompt ke server pihak ketiga.
  - Untuk penggunaan komersial, cek ketentuan layanan Pollinations saat itu sebelum dipakai produksi.
  - Terverifikasi: HTTP langsung 200 (JPEG) dan via gateway Orvyn (job completed → aset tersimpan).
- **Cloudflare Workers AI — provider opsional ketiga (BYO key, ditambahkan 27 Okt):**
  - Free tier akun gratis: ±10.000 neuron/hari (≈50–200 gambar). Butuh account_id + API token yang user isi sendiri.
  - Model default `@cf/black-forest-labs/flux-1-schnell` (output lisensi FLUX-dev-noncommercial? **ceks**: FLUX.1-schnell = Apache-2.0, komersial OK). SDXL opsional (OpenRAIL, batasan penggunaan).
  - **Disabled by default**; prompt dikirim ke server Cloudflare.
  - Status di UI jujur "unconfigured" sampai kredensial valid.
- **Google AI Studio / Gemini Image — provider opsional keempat (BYO key, ditambahkan 27 Okt):**
  - Kunci AI Studio gratis; **kebijakan free tier berubah-ubah** — 27 Okt sebagian model gambar berbayar. Health cek kunci + keberadaan model gambar dan melaporkan apa adanya.
  - Mode: text-to-image + image-to-image (Nano Banana). Prompt/aset dikirim ke server Google. **Disabled by default.**
  - Ketentuan penggunaan output (sintetis, watermark policy) mengikuti Google Terms saat itu.
- **ZeroGPU Space video (modelscope-text-to-video port) — tanpa kunci:**
  - Model ModelScope (lisensi cek repo; model lama 2018-an berbasis re-enable). Video pendek resolusi rendah, kuota ZeroGPU sama dengan provider HF lain.
  - **Disabled by default**; prompt dikirim ke Space pihak ketiga.
- **LTX-Video Distilled Space (Lightricks) — tanpa kunci (ditambahkan 27 Okt):**
  - Kualitas jauh di atas ModelScope: **704×512 @ 30fps**, clip pendek (durasi ≈ frame/24, ±1–6 detik). Terverifikasi anonim end-to-end 27 Okt.
  - Model LTX-Video (Lightricks, open-weights dengan lisensi khusus — cek repo model untuk ketentuan komersial sebelum pakai hasilnya di produksi).
  - Prompt dikirim ke Space pihak ketiga. Kuota ZeroGPU anonim terbatas — Space populer bisa balas `error: null` saat kuota/antre penuh; isi hf_token gratis untuk kuota sendiri.
- **AI Horde — provider kelima, gratis penuh tanpa kunci (ditambahkan 27 Okt):**
  - Jaringan GPU volunteer (Haidra, nonprofit). Key anonim `0000000000`: prioritas rendah, antrean bisa menit-menit, rate limit anonim. Daftar akun gratis memberi kudos/prioritas.
  - Mode: text-to-image + **image-to-image** (img2img). Prompt & gambar sumber dikirim ke worker volunteer — **anggap tidak privat**. Disabled by default dengan konfirmasi.
  - Model menentukan lisensi output: model SD-class OpenRAIL punya batasan penggunaan; worker bebas memilih model sesuai permintaan (default: Horde yang memilih).
  - **Terverifikasi dua kali 27 Okt**: direct anonim (webp 512×512) dan via gateway Orvyn image-to-image (job completed → aset tersimpan).
  - Gotcha: urllib UA default diblok (403) — selalu kirim User-Agent + Client-Agent custom.
- **SiliconFlow — provider keenam, BYO key gratis (ditambahkan 27 Okt):**
  - Free tier saat pengecekan: kredit starter akun baru (±$1 inter / ¥14 .cn) + model `Kwai-Kolors/Kolors` **gratis per gambar**. Kebijakan bisa berubah — cek pricing resmi.
  - Mode: text-to-image + image-to-image (API OpenAI-compatible). FLUX/SDXL tersedia berbayar — tidak jadi default.
  - Prompt/aset sumber dikirim ke server SiliconFlow. **Disabled by default** dengan konfirmasi.
  - Lisensi output mengikuti model yang dipilih (Kolors: cek kartu model Kwai-Kolors).
  - Status jujur "unconfigured" sampai API key diisi di Model & Backend.
- **Tidak diadopsi (riset putaran 2–3, 27 Okt):** HF Inference Providers (kredit gratis user free dihapus Okt 2026 — kini berbayar), fal/WaveSpeed/Kling/Veo/Sora (berbayar), Puter.js (JS-only), web app "gratis" tanpa API, Craiyon (endpoint mati), Perchance (403 anti-bot Cloudflare).
- Fallback lokal (diffusers CPU, model ±2,1 GB, unduh dengan konfirmasi) menjamin fungsi tetap Rp0 saat kuota habis atau offline.
- Biaya jaringan yang tersisa praktis: listrik + kuota internet unduhan model (sekali ±2,1 GB) jika user mengaktifkan fallback lokal.

## 2. Lisensi model (dipakai untuk MODEL_CATALOG; verifikasi ulang sebelum menginstal)

| Model | Lisensi | Komersial | Catatan integritas |
|---|---|---|---|
| Stable Diffusion 1.5 (repo asli `runwayml/...` sudah dihapus di HF; gunakan mirror komunitas atau varian OpenRAIL-M) | CreativeML OpenRAIL-M | Diizinkan dengan batasan penggunaan (daftar prohibited usage di file lisensi) | **Re-check lisensi + digest file saat mendownload.** Jangan klaim model tersedia sebelum backend benar-benar bisa memuatnya |
| DreamShaper 8 (basis SD 1.5) | CreativeML OpenRAIL-M | Diizinkan dengan batasan | varian bergaya; cocok untuk resolusi 512 |
| Realistic Vision (basis SD 1.5) | CreativeML OpenRAIL-M | Diizinkan dengan batasan | alternatif fotorealistis |

Penting: "open-weight" ≠ open-source ≠ bebas komersial. Setiap entri katalog membawa tiga keterangan ini terpisah.

## 3. Lisensi software di stack

| Komponen | Lisensi | Dampak |
|---|---|---|
| Python / pip | PSF | bebas |
| FastAPI, Uvicorn, Pydantic | MIT/BSD | bebas |
| sqlite3 | public domain | bebas |
| PyTorch (wheels CPU resmi) | BSD-3 | bebas |
| diffusers, transformers, accelerate, safetensors | Apache-2.0 | bebas |
| Pillow | MIT-CMU | bebas |
| Node.js / Vite / React / TypeScript | MIT / Apache-2.0 | bebas |
| FFmpeg (build Ubuntu 8.0.1) | LGPL/GPL sesuai config distribusi | bebas untuk pemakaian lokal |
| pytest, httpx | MIT | bebas |

## 4. Yang TIDAK kami klaim

- Hasil model tidak otomatis bebas hak cipta dan tidak otomatis "legal-cleared" untuk iklan; tiap aset menyimpan metadata sumber dan catatan lisensi modelnya.
- Lisensi mirror di HF mengikuti lisensi resmi checkpoint-nya; katalog menyimpan sumber resmi sebagai referensi.
