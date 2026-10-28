# Workflows (dokumen iterasi) — Orvyn

Eksplisit soal status: **Workflows berawalan "rancangan" belum diimplementasikan.** Yang sudah nyata: health, project/asset CRUD, generation gateway + job queue + provider registry, Guided Creation (brief → plan → approval → generation).

## Sudah berjalan
- brief sederhana → Quick Generate (setelah provider aktif) → antrian job → hasil tersimpan + metadata.
- **A1 (tahap 1–4)**: brief terstruktur → Creative Angle Engine (deterministik) → plan preview → edit prompt → approval → N job generation → hasil terregistrasi sebagai aset. **Terverifikasi nyata via ZeroGPU (27 Okt): 3 item → 3 gambar webp.** Pemindahan aset unassigned → project tersedia di Projects & Assets. Recovery job pascarestart aktif.
- **A1 (tahap 5–6)**: campaign bundling aset → overlay typography deterministik (PIL) → export paket zip + manifest sha256 → unduh.
- **A2 (animatic)**: storyboard → scene keyframe (aset gambar) → urutan + durasi → render FFmpeg → MP4 H.264 → asset video. Terverifikasi nyata (durasi tepat, codec h264).
- **Workflow Center (M7)**: pipeline berurutan generate_plan → render_storyboard → export_campaign → manual_check; out-of-order ditolak; failed + retry + skip. Smoke live penuh sukses.
- **Remix & Improve (M5)**: image-to-image via gateway (`source_asset_id` di-resolve server; aset sumber tak pernah berubah). Provider `hf_space_kontext` (FLUX.1-Kontext-Dev, upload file) — jalur HTTP terverifikasi; hasil menunggu kuota ZeroGPU reset. FE page lengkap.
- **Provider gratis tanpa kunci (Pollinations.ai)**: text-to-image gratis, terverifikasi langsung + via gateway (job completed → JPEG tersimpan) — generasi tetap bisa jalan saat kuota ZeroGPU habis.
- **AI Horde (gratis penuh, anonim)**: text-to-image + image-to-image; **terverifikasi via gateway** (i2i completed → webp 512×512 tersimpan). Antrean bisa menit-menit (trade-off gratis yang jujur).
- **Text-to-Video (hf_space_video)**: Space ModelScope t2v tanpa kunci; mode video di QuickGenerate; jalur terverifikasi s/d pesan kuota resmi Space (hasil menunggu reset kuota harian).
- **Studio Prompt (tab kedua di Quick Generate)**: brief terstruktur (subjek → shot → negative space → style → lighting → mood) → mega prompt dasar konsisten + varian beda style/angle; tiap varian tombol **Generate** (pilih provider) dan **Salin** (coba di tool lain). Terverifikasi end-to-end via AI Horde.
- **BYO key gratis**: Cloudflare Workers AI (flux schnell) + Google AI Studio/Gemini (gambar + revisi i2i) + SiliconFlow (Kolors gratis per gambar + i2i) — diaktifkan setelah user isi kredensial di Model & Backend (health jujur "unconfigured" sampai kredensial valid).
- **Video kualitas tinggi**: LTX-Video Distilled (704×512 @ 30fps) — aktif tanpa kunci; durasi pendek (frame/24). Kuota ZeroGPU anonim terbatas; isi hf_token gratis untuk kuota lebih lega.

## Rancangan (belum implementasi)
- **A1 lanjutan**: review/compare hasil antar angle, template overlay, versi kampanye.
- **A2 lanjutan**: crossfade antar scene, audio track, image-to-video (bila provider terverifikasi — tetap tidak dibangun boneka).
- (opsional) diffusers lokal SD1.5 fp16 (unduhan ±2,1 GB, perlu konfirmasi user) — cadangan offline tanpa kuota.

Spesifikasi lengkap di prompt master (Milestone 4–7) — diimplementasikan bertahap dan ditandai di `IMPLEMENTATION_PLAN.md`.
