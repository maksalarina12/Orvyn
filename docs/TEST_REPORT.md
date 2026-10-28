# Test Report — Orvyn

Terakhir dijalankan: 27 Okt 2026 (sembilan kali), pada Ubuntu 26.04.1, Python 3.13, Node 24.

## Backend (pytest)

Hasil: **84 passed, 0 failed**. Perintah: `scripts/test.sh`.

Cakupan yang teruji:

- Health: status nyata (storage/memory/ffmpeg/database/inference) — `test_health.py`
- Root/config endpoint — `test_health.py`
- Projects: CRUD lengkap, validasi (nama kosong/kategori salah), delete memerlukan `confirm=true`, delete proyek melepas asset tanpa menghapus file — `test_projects.py`
- Assets: upload PNG (metadata lebar/tinggi nyata via PIL), serve file bytes, favorite/notes, hapus dengan file opsional; tolak tipe tak dikenal (415); tolak >50 MB (413); project harus ada (400); filter list — `test_assets.py`
- Path safety: traversal ditolak, file nyata pada base tmp lolos — `test_path_safety.py`
- Diajnostik: `_inference_backend` jujur menyatakan runtime belum pasang — `test_diagnostics.py`
- Generation gateway: listing provider jujur (disabled + alasan), enable eksternal butuh `confirmed_external=true`, enable unconfigured ditolak, submit saat provider mati → 409, validasi params → 422, lifecycle job (queued→completed + asset terregistrasi + file PNG tersimpan), cancel job queued, provider gagal → `failed` dengan attempts=2 dan error tercatat — `test_generation.py`
- **Guided Creation (M3)**: preview plan deterministik (brief sama → item sama), validasi kategori → 422, persist draft + get, approve tanpa provider aktif → 409, approve membuat tepat N job untuk N item dan tiap job menghasilkan tepat 1 aset (jumlah job = jumlah output), edit item hanya saat draft (setelah approve → 409, hapus → 409), hapus draft — `test_plans.py`
- **Recovery pascarestart**: job `running` saat backend mati dengan sisa attempt → di-queue ulang dengan pesan jujur; tanpa sisa attempt → `failed` dengan pesan jujur — `test_plans.py`
- **Pindah aset antar project**: PATCH `project_id` pindah, string kosong melepas ke unassigned, project tak dikenal → 400 — `test_assets.py`
- **Storyboard & animatic (M6)**: probe FFmpeg melaporkan codec/dimensi/durasi nyata; CRUD storyboard + validasi aspect/fps; aturan scene (durasi 0,5–10 s → 400/422, asset tak ada → 400, keyframe harus gambar → 400); reorder via idx; render storyboard kosong → 400; **render animatic menghasilkan MP4 H.264 nyata** (magic bytes `ftyp`, ffprobe durasi sesuai total scene, terregistrasi sebagai asset `source=render`) — `test_storyboards.py`
- **Campaign Studio (M4)**: CRUD + status (draft/active/completed, salah → 400); bundling aset eksplisit (asset tak ada → 400, urutan stabil); overlay PIL → asset baru `source=overlay, revision_of` benar + piksel band terverifikasi berubah; overlay aset di luar campaign → 400; validasi posisi/teks → 422; **export zip nyata** berisi aset + manifest.json (sha256 per file) + unduhan stream — `test_campaigns.py`
- **Workflow Center (M7)**: CRUD + validasi kind; **step hanya bisa dijalankan berurutan** (out-of-order → 400); step failed jujur tersimpan (provider mati / export kosong) + retry → sukses; manual_check run/skip; render_storyboard step menghasilkan video asset nyata; export step done → workflow `done` — `test_workflows.py`
- **Provider gratis + image-to-image (M5/M8)**: caps & validasi Pollinations (tanpa network); Pollinations menolak mode salah; default config Kontext + validasi file sumber (ada/tiada); Kontext menolak mode salah; gateway: i2i tanpa `source_asset_id` → 400, aset tak ada → 404, aset video → 400, **injeksi `input_image` dari klien dibuang** — `test_providers_free.py`
- **Provider video + BYO key (M9 riset)**: magic-sniff media (mp4/webm/jpeg/webp); Space video default + validasi num_frames/steps/seed; video menolak mode gambar; Cloudflare: schema config (account_id wajib, token secret), validasi param + health jujur `unconfigured` tanpa kredensial, tolak mode video; Google AI Studio: schema config, caps text+image-to-image, health jujur `unconfigured`; **gateway menerima mode `text_to_video`** — `test_providers_video_byo.py`
- **AI Horde (M9 riset putaran 2)**: caps text+image-to-image; validasi kelipatan 64/steps/seed/denoising; tolak mode video; i2i wajib file sumber; key anonim opsional (kosong = `0000000000`) — `test_aihorde.py`
- **Generasi nyata t2v (bugfix sesi)**: job_877869c4d7f2 COMPLETED ±30s → ast_6f1a2d050015 mp4 46KB; bug mode/provider di Quick Generate diperbaiki (sinkronisasi mode otomatis)
- **SiliconFlow (M9 riset putaran 3)**: caps text+image-to-image; validasi ukuran/steps/seed/format model `org/nama`; tolak mode video; health jujur `unconfigured` tanpa key — `test_siliconflow.py`
- **Prompt Studio (mode kedua Quick Generate)**: meta lengkap; build deterministik & anchor subjek konsisten di semua varian; klause negative space (muncul saat != none); varian style/angle/both berbeda dari dasar; tolak nilai tak dikenal & count di luar 1–6; endpoint meta 200 + preview 200/422 — `test_prompt_studio.py`
- **LTX-Video Distilled (video kualitas tinggi)**: default Space benar (ModelScope tidak bocor); mapping 13 parameter (duration = frame/24, randomize otomatis saat tanpa seed); validasi frame 8–96, w/h kelipatan 32, guidance 1–5, num_images 1–2; tolak mode selain text_to_video — `test_ltx_video.py`

Catatan: provider kamu dalam `test_generation.py` adalah **test fixture** (menulis PNG via PIL) untuk uji mekanika job — diberi label `test suite only` dan tidak pernah diregistrasi di UI produksi.

## Frontend

- `npm run build` (tsc strict + vite): **PASS** (49→… →187 kB gzip 60 kB).
- Belum ada test otomatis UI; Smoke test manual: backend 8187 merespons, frontend 5170 memuat (HTTP 200), halaman Dashboard/Projects/QuickGenerate/ModelSettings menampilkan data nyata.

## Yang BELUM terverifikasi (jujur)

1. **Generasi lokal diffusers end-to-end** — butuh konfirmasi user untuk unduhan ±2,1 GB.
2. **Approve plan Guided Creation via ZeroGPU nyata** — jalur approval → job teruji di pytest (test provider); eksekusi nyata via `hf_space` menunggu kuota/token (jalur generation-nya sendiri sudah terverifikasi 26 Okt).
3. Video assembly FFmpeg (direncanakan Milestone 6).

## Verifikasi generasi nyata (26–27 Okt 2026)

1. **Direct Gradio v5 REST ke `black-forest-labs/FLUX.1-schnell` (ZeroGPU)**: ✓ submit → `event_id` → poll SSE → gambar webp tersimpan. Pipeline jaringan/unduhan nyata TERVERIFIKASI.
2. **Via gateway Orvyn (`POST /api/generations` dengan `hf_space`)**: job queued→running→failed dengan error provider asli apa adanya (`Space gagal memproses: null` = kuota ZeroGPU anonim habis setelah percobaan pertama, 26 Okt). Perilaku honest.
3. **Guided Creation approve via ZeroGPU (27 Okt)**: plan 3 item → approve → 3 job **completed** → 3 webp 640×352 tersimpan. Jalur brief→plan→approve→generate TERVERIFIKASI penuh.
4. **Pollinations.ai via gateway (27 Okt)**: job text_to_image → **completed** → JPEG 512×512 tersimpan (`ast_6b4c2415e50d`). Gratis tanpa kunci — generasi tetap jalan meski kuota ZeroGPU habis.
5. **Kontext img2img (27 Okt)**: upload file → 200, call/infer → 200 (event_id); GPU menolak karena kuota ZeroGPU anonim habis (`Space gagal memproses: null`) — jalur terverifikasi s/d tahap GPU, hasil menunggu reset kuota.
6. **Video t2v via Space ModelScope (27 Okt)**: endpoint `/generate` terverifikasi (call → event_id 200); Space membalas dengan pesan kuota resmi ZeroGPU ("exceeded your ZeroGPU quota (90s requested vs. 0s left)") — jalur jalan penuh s/d GPU, menunggu reset kuota.
7. **AI Horde (27 Okt)**: DUA verifikasi nyata — (a) direct anonim: submit → antrean → worker → webp 512×512 unduh; (b) **via gateway Orvyn image_to_image: job completed → aset webp 512×512 tersimpan** (`ast_135865b56d09`). Revisi gambar gratis bekerja hari ini.
8. Kesimpulan: jalur generation nyata end-to-end dengan API gratis; Cloudflare/Google AI Studio siap pakai setelah user mengisi kredensial gratis (health jujur "unconfigured" sampai itu).
