# Implementation Plan — Orvyn

> **STATUS SAAT INI** — bagian ini di-update di akhir setiap sesi agar pekerjaan bisa dilanjutkan tanpa kehilangan konteks.

## Status per milestone

| Milestone | Status | Catatan singkat |
|---|---|---|
| M0 — Environment audit | **DONE** (26 Okt 2026) | Hasil di `HARDWARE_ASSESSMENT.md`: laptop i5-8365U, iGPU UHD 620, **tanpa CUDA**, RAM 7,1 GiB, disk bebas 63 GB, FFmpeg 8 ada, tidak ada ComfyUI/model |
| M1 — Functional app shell | **DONE** | Backend FastAPI+SQLite (health nyata, projects/assets CRUD, upload+magic bytes, path safety) + FE shell 9 modul + 22 pytest PASS + build FE hijau |
| M2 — Quick Generate | **DONE** | Gateway + queue + provider registry + adapter ZeroGPU teruji (direct Gradio v5 nyata ✓). **Approve plan via ZeroGPU terverifikasi 27 Okt**: 3 item plan → 3 job completed → 3 webp 640×352 tersimpan |
| M3 — Guided Creation | **DONE (inti)** | Brief form per kategori + Creative Angle Engine deterministik (tanpa LLM) + prompt builder data-driven + plan preview + approval (draft → approved → N job). Recovery job pascarestart + pindah aset unassigned → project selesai di sesi ini. Sisa: verifikasi approve via ZeroGPU nyata saat kuota tersedia |
| M4 — Campaign Studio | **DONE (inti)** | Campaign CRUD + bundling aset eksplisit + overlay typography deterministik via PIL (posisi/font/warna, hasil = asset baru `source=overlay, revision_of`) + export paket zip + manifest.json dengan sha256 per file + unduhan via API. Sisa: review/compare antar angle, template overlay |
| M5 — Remix & Improve | **DONE (inti)** | Jalur `image_to_image` via gateway (`source_asset_id` di-resolve server, path injection diblok). Provider: `hf_space_kontext` (FLUX.1-Kontext-Dev, upload file → FileData; upload+call endpoint terverifikasi HTTP 200; hasil menunggu kuota ZeroGPU reset — kuota anonim habis hari ini, error dilaporkan jujur). FE `RemixImprove.tsx`: pilih sumber → instruksi → job → polling → hasil |
| M6 — Storyboard & Video | **DONE (animatic)** | Storyboard CRUD + scene editor (keyframe dari aset gambar) + render animatic MP4 nyata via FFmpeg 8 (H.264, scale/pad/fps/yuv420p, faststart, concat). Generative video tetap NOT feasible lokal — sesuai keputusan. Sisa: crossfade/transisi, audio, ekspor paket |
| M7 — Workflow Center | **DONE (inti)** | Pipeline berurutan atas modul terverifikasi: step `generate_plan` (approve → job), `render_storyboard` (animatic), `export_campaign` (zip), `manual_check`. Run hanya step aktif berikutnya (out-of-order → 400), step failed jujur + retry, skip, reorder. Smoke live penuh sukses: 4 step → workflow done |
| M8 — Hardening | **DONE (dasar)** | Batas upload ada (MAX_UPLOAD_MB, streaming); `input_image` hanya bisa di-set server; cleanup export >7 hari saat startup; pesan error eksternal apa adanya; tidak ada shell exec; semua path divalidasi |

## Keputusan arsitektur yang sudah final

- FastAPI + SQLite (stdlib) + file assets di `data/`.
- Frontend React+TS+Vite, CSS murni, port dev 5170; backend Uvicorn di `127.0.0.1:8187`.
- **Generation Gateway + provider registry** (keputusan 26 Okt 2026, evolusi kebijakan awal):
  - Semua generasi masuk satu job queue dengan adapter interface yang sama (`backend/backends/`).
  - Provider image pertama: **Hugging Face ZeroGPU Spaces (Gradio API)** — gratis dengan kuota ±5 menit GPU/hari (≈10–30 gambar SD-class). Cocok untuk prototipe; status kuota/gagal ditampilkan jujur di UI.
  - Provider fallback permanen: **diffusers CPU lokal SD1.5-class fp16** (±2 GB model, butuh konfirmasi download) — digunakan saat kuota habis/offline; bukan pengganti kecepatan.
  - Provider video generatif: **tidak dikonfigurasi** sampai ada Space yang benar-benar diverifikasi end-to-end. Sampai itu, video hanya via FFmpeg assembly (terverifikasi ada).
- Provider eksternal: disabled by default, butuh persetujuan user sebelum pengiriman pertama (data prompt/aset dikirim ke pihak ketiga), tidak pernah otomatis.
- FFmpeg assembly nyata = alur video utama; AI-video dianggap tidak tersedia di hardware ini (tidak dibangun boneka).
- Lisensi per-Space/model dicatat di katalog sebelum dipakai; Space bisa berubah/hilang, UI tidak boleh menghardcode angka kuota statis sebagai kepastian.

## Gates yang butuh konfirmasi user

1. **Download model SD 1.5-class fp16 ±2,1 GB** sebelum M2 bisa uji generasi nyata. (setup dapat dijalankan tanpa model — Quick Generate akan menampilkan pesan manageable "model belum terpasang".)
2. Tidak ada operasi privileged lain yang direncanakan. Semua pip-install di venv proyek (reversible, tanpa sudo).

## Yang baru selesai (urutan eksekusi sesi ini)

1. Audit Sistem Ubuntu (read-only) — selesai, terdokumentasi.
2. Dokumen: HARDWARE_ASSESSMENT, ARCHITECTURE, COST_AND_LICENSES, TEST_REPORT, INSTALLATION, TROUBLESHOOTING, MODEL_CATALOG, WORKFLOWS (+ PLAN ini di-update berjalan).
3. Scaffolding + `.gitignore` + README + `scripts/{check-system,setup,start,stop,test}.sh` (semua idempotent, no-sudo, tanpa unduhan model).
4. Backend M1: FastAPI + SQLite + health (data nyata) + projects CRUD + assets (upload mimes/ukuran/dim) + path safety — pytest hijau.
5. Keputusan arsitektur diperbarui setelah diskusi: Generation Gateway + provider registry; ZeroGPU Spaces opsional; diffusers CPU fallback permanen.
6. **Milestone 2 inti**: `backend/backends/{base,registry,provider_settings,gradio_space}.py`, `backend/jobs/service.py` (queue, concurrency 1, retry ≤2, cancel, registration aset otomatis), API `/api/providers*` + `/api/generations*`, engine dijalankan di lifespan FastAPI.
7. Frontend nyata terhubung: QuickGenerate (submit job, polling 2 s, cancel, hasil), ProjectsAssets (CRUD), ModelSettings (aktif/nonaktif provider dengan konfirmasi eksternal), Dashboard (status nyata).
8. Smoke test live: backend 8187 OK, FE 5170 OK, listing provider jujur "disabled", enable tanpa konfirmasi → 400, submit tanpa provider aktif → 409.
9. **22 backend test PASS**, frontend `npm run build` PASS. Detail: `docs/TEST_REPORT.md`.
10. **E2E sukses lewat Orvyn sendiri**: job `job_b8e24f8f6214` (prompt user: iklan meja belajar, kamar mewah, jendela sunset) → completed → asset webp 640×352 tersimpan (`data/outputs/unassigned/job_b8e24f8f6214/`). Kuota anonim ZeroGPU pernah habis (error asli tampil jujur), reset harian menyelesaikan.
11. Sidebar fix: indikator kini "Space provider aktif" saat provider eksternal siap, meski runtime lokal belum pasang.

## CATATAN RESUME (27 Okt 2026 — sesi M3)

Aplikasi dijalankan dengan:
```bash
cd ~/Documents/repo/Orvyn && bash scripts/start.sh
```
(UI http://127.0.0.1:5170 • API http://127.0.0.1:8187/docs)

State provider: `hf_space` AKTIF + terkonfigurasi (FLUX.1-schnell, ZeroGPU; api_name=infer; input_keys=[prompt,seed,randomize_seed,width,height,steps]; FLUX.1-schnell TIDAK mendukung negative prompt/guidance). Matikan dari UI Model & Backend bila diinginkan.

Yang selesai di sesi 27 Okt (M3 + prioritas lama):
1. **M3 Guided Creation**: `backend/prompts/builder.py` (prompt builder data-driven, deterministik), `backend/creative_planning/engine.py` (11 angle, urutan per-kategori, rotasi seed sha256 dari brief), `backend/creative_planning/service.py` (plans: draft → approved, 1 item = 1 job = 1 output), `backend/api/plans.py` (preview/create/list/get/patch item/approve/delete), schema v3 (`creation_plans`, `creation_plan_items`), FE `GuidedCreation.tsx` penuh (form → preview → draft → edit prompt per item → approve → polling status job 2,5 s).
2. **Recovery pascarestart**: `recover_stale_jobs()` di `jobs/service.py`, dipanggil di lifespan sebelum engine start; `running` saat mati → requeue bila ada sisa attempt, else `failed` jujur.
3. **Pindah aset**: `ProjectsAssets.tsx` kini menampilkan aset terbaru + dropdown pindah ke project (unassigned bisa di-assign); PATCH `/api/assets/{id}` sudah ada.
4. **32 pytest PASS**, `npm run build` PASS. Smoke live: preview prompt natural, draft + edit item OK, approve provider tak dikenal → 409. Satu draft contoh tersisa: `plan_4c9d63f9136c` ("Demo Meja Belajar") — bisa di-approve dari UI saat kuota ZeroGPU tersedia, atau dihapus.

Yang selesai di sesi 27 Okt (lanjutan — M6 animatic):
5. **M6 Storyboard & Video (animatic)**: `backend/media/ffmpeg.py` (probe + segment/concat builder, structured args tanpa shell concat), `backend/storyboards/service.py` (CRUD storyboard + scene: add/update/reorder/remove, aturan keyframe harus gambar, durasi 0,5–10 s, maks 30 scene), `backend/api/storyboards.py` (router penuh + `/meta` + `POST .../render` sinkron), schema v4 (`storyboards`, `storyboard_scenes`), FE `StoryboardVideo.tsx` (list + create + scene editor dengan thumbnail/reorder/durasi + render + video player). Hasil render diregistrasi sebagai asset video (source=render) — tampil di Projects & Assets.
6. **38 pytest PASS** (6 baru: probe metadata nyata, CRUD, validasi scene, reorder, render MP4 nyata dengan ffprobe cek durasi/codec, tolak video keyframe), `npm run build` PASS.
7. **Smoke live render**: storyboard 2 scene (1,0 s + 1,5 s) → MP4 H.264 640×360 durasi tepat 2,50 s, terregistrasi sebagai asset. Storyboard contoh: `sb_d8501e66831d` ("Smoke Animatic").

Yang selesai di sesi 27 Okt (lanjutan — M4 Campaign Studio):
8. **M4 Campaign Studio**: `backend/campaigns/service.py` (CRUD + bundling aset eksplisit + registrasi overlay), `backend/media/overlay.py` (typography deterministik PIL: wrap teks, band semi-transparan, posisi top/center/bottom, warna hex, DejaVuSans-Bold + fallback), `backend/exports/service.py` (zip + manifest.json berisi metadata + sha256 per file), `backend/api/campaigns.py` (router penuh + overlay + export/download), schema v5 (`campaigns`, `campaign_assets`), FE `CampaignStudio.tsx` (list + editor: status, bundling aset, tool overlay dengan color picker, export + unduh).
9. **43 pytest PASS** (5 baru: CRUD + status, aturan bundling, overlay → asset baru revision_of, validasi overlay, export zip + manifest + unduhan), `npm run build` PASS.
10. **Smoke live M4**: campaign berisi PNG + animatic MP4 → overlay "Kopi Pagi Hari" (revision_of benar) → export zip 3 aset + manifest sha256 terverifikasi. Campaign contoh: `cmp_322ff2e9d065` ("Launch Kopi Smoke").

Yang selesai di sesi 27 Okt (lanjutan — M7 + verifikasi ZeroGPU):
11. **Verifikasi ZeroGPU via approve plan**: plan `plan_4c9d63f9136c` (3 item) → approve via `hf_space` → 3 job completed → 3 webp 640×352 di `data/outputs/unassigned/plan_4c9d63f9136c/`. Jalur M3 end-to-end TERVERIFIKASI nyata.
12. **M7 Workflow Center**: `backend/workflows/service.py` (pipeline berurutan: run hanya step aktif berikutnya; failed jujur + retry; skip; reorder; dispatch ke plan/storyboard/campaign services), `backend/api/workflows.py`, schema v6 (`workflows`, `workflow_steps`), FE `WorkflowCenter.tsx` (timeline + add step dengan ref picker kontekstual + run/skip/retry + provider select). Catatan bug penting: exception di dalam `db_session` me-rollback — status failed step kini disimpan tanpa raise (return workflow apa adanya).
13. **49 pytest PASS** (6 baru), `npm run build` PASS.
14. **Smoke live M7**: workflow 4 step (generate_plan via hf_space → render_storyboard → export_campaign → manual_check) → semua done, workflow done. Out-of-order run ditolak 400. Contoh: `wf_c158b9c1082d`.

Prioritas lanjutan:
1. **Verifikasi ulang img2img Kontext saat kuota ZeroGPU reset** (besok): approve plan / job revisi akan otomatis jalan — jalur upload+infer sudah terverifikasi HTTP, hanya GPU-nya yang kena limit hari ini.
2. (opsional, butuh konfirmasi user) Fallback lokal diffusers SD1.5 fp16 — unduh ±2,1 GB (cadangan offline, tanpa kuota).
3. M6/M7 lanjutan: crossfade antar scene, audio track, review/compare hasil antar angle.
4. Kuota ZeroGPU anonim terbatas — token HF gratis via UI/env untuk kapasitas lebih.

Riwayat sesi 27 Okt (tahap "semua fitur + API free"):
15. **Provider Pollinations.ai** (gratis tanpa kunci, Classic API): terverifikasi langsung (HTTP 200, JPEG) **dan via gateway Orvyn** (job completed → aset JPEG 512×512 tersimpan). Enabled + health ok.
16. **Provider `hf_space_kontext`** (FLUX.1-Kontext-Dev, image-to-image): adapter upload file Gradio (multipart → FileData), endpoint upload+call terverifikasi 200; GPU ditolak kuota anonim (jujur). `requires_config=False` (default Space).
17. **M5 Remix & Improve**: gateway mode `image_to_image` + `source_asset_id` (resolve server-side; injection diblok; bukan gambar → 400), FE page lengkap (pilih sumber → instruksi → job → polling → hasil). Bug fix: urutan validasi (resolusi sumber sebelum validate_params).
18. **M8 Hardening dasar**: cleanup export lama di startup, batas upload streaming sudah ada, review jalur injeksi path.
19. **56 pytest PASS** (7 baru), `npm run build` PASS.
20. **Riset + integrasi API free tambahan (M9-lite)**: hasil riset web — provider gratis nyata: Pollinations (sudah ✓), ZeroGPU Spaces (sudah ✓), Cloudflare Workers AI (10.000 neuron/hari, BYO key), Google AI Studio/Gemini (BYO key), video = ZeroGPU Space. Provider yang dijual "free API" lain (fal, WaveSpeed, Kling, Veo/Sora) ternyata berbayar; Puter.js = JS-only, tidak bisa dari backend. Ditambahkan:
    - **`hf_space_video`** — text-to-video tanpa kunci (default: `mediasynthesismuseum/modelscope-text-to-video`, endpoint `/generate`, params [prompt, seed, num_frames, steps], output mp4). Magic-sniff media (mp4/webm). Call endpoint terverifikasi 200; GPU masih kena kuota harian (error resmi Space tampil jujur). FE QuickGenerate dapat pilihan mode Video.
    - **`cloudflare`** — BYO key gratis (account_id + api_token), model `@cf/black-forest-labs/flux-1-schnell` (JSON base64) + SDXL (raw). Health probe `ai/models/search` dengan pesan jujur "unconfigured" sampai kredensial diisi.
    - **`google_ai_studio`** — BYO key gratis; modes text_to_image + image_to_image (Nano Banana). Health cek `models?key=` + keberadaan model gambar.
    - **FE settings generik**: config fields per provider dari `capabilities.config_schema` (password untuk secret, wajib-vs-opsional, redacted `<set>`); QuickGenerate mode select + render video (`<video>`).
21. **63 pytest PASS** (7 baru), build FE hijau.
22. **Riset putaran 2 + AI Horde (M9-lite lanjutan)**: HF Inference Providers tak lagi gratis (kredit free user dihapus Okt 2026) → skip. **AI Horde** (jaringan GPU volunteer Haidra) diintegrasi: anonim tanpa kunci (`0000000000`), modes text_to_image + **image_to_image** (img2img base64), antrean async + poll, hasil URL-signed atau base64 (dua-duanya ditangani). **Terverifikasi end-to-end DUA KALI**:
    - Direct: submit anonim → worker generate → webp 512×512 unduh nyata.
    - Via gateway Orvyn: **job image_to_image completed → aset webp 512×512 tersimpan** (`ast_135865b56d09`) — jalur revisi gambar gratis yang bekerja hari ini juga (ZeroGPU Kontext masih menunggu kuota).
    Gotcha: urllib default UA diblok Horde (403) — provider mengirim `User-Agent` + `Client-Agent` custom; worker boleh membulatkan ukuran minta.
23. **67 pytest PASS** (4 baru: caps/validasi Horde, tolak mode video, i2i wajib sumber, magic-sniff), FE: mode i2i dihilangkan dari QuickGenerate (jalur i2i lewat halaman Remix & Improve).
24. **Riset putaran 3 + SiliconFlow (M9-lite)**: kandidat keyless Craiyon (koneksi gagal) & Perchance (403 Cloudflare) — dieliminasi. **SiliconFlow** diintegrasi (BYO key gratis): free tier = kredit starter + model `Kwai-Kolors/Kolors` gratis per gambar (saat pengecekan); modes text_to_image + image_to_image (API OpenAI-compatible, base .com bisa dioverride ke .cn). Health cek kunci nyata — "unconfigured" jujur sampai key diisi.
25. **70 pytest PASS** (3 baru), build FE hijau. Total 8 provider.
26. **Studio Prompt (mode kedua Quick Generate)** — backend `prompt_studio/service.py` (stateless, deterministik): brief terstruktur (subject, shot, placement negative-space, style, lighting, mood, extra) → **mega prompt dasar dengan anchor subjek konsisten** + varian (beda style / beda angle / keduanya, 1–6). Endpoint `/api/prompt-studio/meta` + `/preview` (422 jujur). FE `components/PromptStudio.tsx`: tab Langsung|Studio di QuickGenerate; kartu varian dengan **Generate (pilih provider) + Salin (clipboard)** + hasil inline per kartu; pengaturan generate bersama (aspect/steps/seed/jumlah). **Smoke live terverifikasi**: preview 2 varian → generate varian style_analog via ai_horde → job_15749756c267 COMPLETED → ast_fba365f06e70 webp 512×512.
27. **80 pytest PASS** (10 baru: deterministik, anchor konsisten, klause negative space, varian style/angle/both, batas count, endpoint 200/422), build FE hijau.
28. **Redesign visual "Meja Kontrol Darkroom"** (skill anti-ai-slop): riset Darkroom (darkroom.co) + mission-control/amber telemetry + Palantir-style; kontrak desain di `.design/DESIGN.md` (sumber kebenaran) + `REFERENCES.md` + `AUDIT.md`. Tokens baru: warm near-black (#121110–#2b2721), amber safelight #eda63e hanya interaksi/fokus, Archivo + JetBrains Mono (fallback offline), radius 3-4px, tanpa shadow, focus-visible amber, reduced-motion, sidebar rail horizontal <920px. Navbar bernomor mono 01–09, brand mark amber solid, StatusPill tag persegi mono, semua label form jadi micro-label uppercase, prompt readout mono. Nama kelas JSX tidak berubah (kecuali Sidebar: nav-dot → nav-index). 80 pytest PASS tetap, build hijau.
29. **Perf: /api/providers dari 6,6s → 16ms cached / 1,8s cold.** Akar: health check jaringan (3 Space HF + Pollinations + AI Horde) berurutan per request, ditambah jalur refresh yang juga berurutan (keliru). Fix di `registry.py`: cache health TTL 30s (`_fresh_health`), health check paralel ThreadPoolExecutor(8) untuk kedua jalur, `invalidate_health()` saat enable/disable config berubah, endpoint `GET /api/providers?refresh=true` untuk pemeriksaan paksa. Debug: `ORVYN_HEALTH_DEBUG=1` mencetak durasi tiap probe ke logs/backend.log. 80 pytest PASS.
30. **Bugfix Quick Generate: ganti provider tidak menggeser mode** — state `mode` tetap `text_to_image` padahal dropdown visual menampilkan "Video (t2v)" (satu-satunya opsi), job terkirim salah mode (2 attempt gagal, error jujur). Fix: efek sinkron `mode` ↔ `capabilities.modes` provider terpilih (auto-pindah ke text_to_image/text_to_video yang didukung) + guard di submit. **Video t2v live terverifikasi**: job_877869c4d7f2 COMPLETED ±30s → ast_6f1a2d050015 mp4 46KB (kasur luxury, zoom out) — kuota ZeroGPU anonim sudah reset.
31. **Provider video kualitas tinggi: LTX-Video Distilled** (`hf_space_video_ltx`, subclass GradioSpaceVideoProvider): 704×512 @ 30fps (vs ModelScope 256×256 @ 8fps), endpoint `text_to_video` dengan 13 parameter (negative_prompt, guidance, duration = frame/24, randomize saat tanpa seed). **Terverifikasi anonim end-to-end**: output mp4 704×512 di-upload sebagai ast_71d36db8d5cc. Validate: frame 8–96, w/h kelipatan 32, guidance 1–5, num_images 1–2. Gotcha yang ditemukan: subclass `_settings()` HARUS bypass default parent (`GradioSpaceProvider._settings(self)`) supaya space_url ModelScope tidak bocor. 84 pytest PASS (4 baru). Catatan kuota: setelah LTX sukses sekali, kuota ZeroGPU anonim IP habis — pesan asli "ZeroGPU quota exceeded, 0s left"; Space populer (LTX/Cog/Wan) balas `error: null` saat kuota/antre penuh, ModelScope balas pesan kuota eksplisit. Solusi: tunggu reset harian atau isi hf_token gratis di Model & Backend (provider sudah baca `hf_token`).

Gotcha yang sudah diketahui:
- JANGAN `pkill -f uvicorn` dari terminal di repo (cmdline shell ikut mengandung kata itu → shell bunuh dirinya). Gunakan `scripts/stop.sh` atau kill PID dari `data/cache/*.pid`.
- `npm install` postinstall esbuild kadang butuh `npm approve-scripts esbuild rebuild` (frontend).
- Container docker user (mis. PID 3016 `npm run start`) bukan milik Orvyn — jangan diganggu.
- Approve plan mengirim N prompt sekaligus ke provider aktif — dengan ZeroGPU anonim, kuota ±5 menit GPU/hari bisa habis di 3–4 item.

## Langkah berikut (pilih sesuai persetujuan user)
- (opsional) Unduhan fallback lokal SD1.5-class fp16 ±2,1 GB (perlu konfirmasi).
- Verifikasi approve plan via ZeroGPU nyata (kuota memungkinkan).
- Milestone 4 Campaign Studio (paket aset + overlay typography).


## Roadmap ringkas M1→M3

- M1: backend health + projects/assets CRUD + schema + pytest; frontend shell 9 modul + Dashboard dari data nyata.
- M2: adaptor diffusers + jobs + integrasi Quick Generate. Model download setelah konfirmasi.
- M3: Guided Creation dengan Angle Engine deterministik + prompt builder data-driven, tanpa keharusan LLM.

### 32. Redesign pass 2 — "Instrument Board" (27 Okt 2026)

- Top rail telemetri baru (`components/TopRail.tsx`) + `AppLayout` dibungkus `.shell-main`; status backend dipindah dari `Sidebar.tsx` (kini footer mono LOCAL-FIRST).
- Dashboard direstruktur: grid SYSTEM CHECK / MULAI KERJA, job log nyata (`api.jobs`, `GET /api/generations?limit=6`), filmstrip output, daftar proyek — semua data asli tanpa placeholder.
- CSS: `.toprail`, `.sec-head`, `.readout-row`, `.quick-grid`, `.job-row`, `.filmstrip`, `.kicker`; h1 25px; responsive <920px & <860px & <520px.
- Timeout health probe `cloudflare.py` diseragamkan ke `httpx.Timeout(5, read=10)` (semua provider kini sama).
- Verifikasi: `npm run build` hijau, 84 pytest PASS, FE 200.

### 33. Redesign total — "Studio Cetak" (27 Okt 2026)

- Tema diganti dari darkroom amber ke editorial terang: paper `#f1ebdd`, ink `#161410`, red `#b23a22`; font Newsreader + IBM Plex Sans + IBM Plex Mono.
- `Sidebar.tsx` & `TopRail.tsx` dihapus, diganti `Masthead.tsx` (brand + telemetri + nav bernomor dua baris); `AppLayout` disederhanakan.
- `styles.css` ditulis ulang penuh (±640 baris) mencakup seluruh 9 halaman; panel tanpa kotak, tabel garis, kontrol persegi.
- QA visual via Chrome headless (dashboard, quick generate, guided, projects, workflows, models, mobile 390px); cacat nav/disabled/grid diperbaiki.
- Verifikasi: `npm run build` hijau; backend tidak berubah.

### 34. Redesign pass 4 — "Werkstatt" + akselerator workflow (27 Okt 2026)

- Tema baru netral dingin + cobalt; font Instrument Sans + JetBrains Mono; `styles.css` ditulis ulang penuh.
- `Shell.tsx`: rail ciut/lebar (persist), topbar status, bottom nav mobile; `Masthead.tsx` dihapus.
- `CommandPalette.tsx`: `Ctrl/⌘+K`, pencarian halaman/aksi, navigasi panah/Enter, dialog `?`, Esc/backdrop close.
- Shortcut global `1–9` + guard input/dialog; `⌘⏎` submit di Quick Generate.
- `lib/promptHistory.ts` + chip riwayat prompt (8 entri, localStorage, bisa dihapus).
- QA via Chrome DevTools Protocol membuktikan alur palette dan shortcut; build hijau, 84 pytest PASS.

### 35. Scrollbar hilang + smooth scroll (27 Okt 2026)

- Scrollbar global disembunyikan via CSS (`scrollbar-width: none` + `::-webkit-scrollbar`), scroll tetap berfungsi.
- Hook `useSmoothScroll` di `Shell` untuk wheel dengan easing (0.62 / 0.085), guard kontainer dalam, palette, touch, dan reduced-motion.
- Verifikasi CDP: scrollbar 0px, y 0→186 dengan easing, palette list scroll tanpa menggeser halaman; build hijau.

### 36. Palet hangat + collapse rail (27 Okt 2026)

- Token warna dikembalikan ke palet kertas/tinta/merah (Studio Cetak) sambil mempertahankan shell & densitas Werkstatt.
- Rail: toggle 26px, `aria-expanded`, pintasan `⌘B`/`Ctrl+B` (terdaftar di dialog `?` dan palette), footer disembunyikan saat ciut.
- Verifikasi CDP: 224 → 60 → 224 + persist localStorage; build hijau.


### 37. Pratinjau popup + tombol Unduh (27 Okt 2026)

- Komponen `AssetPreview` (gambar/video) dengan metadata API, prompt + salin, Unduh, dan penutup Esc/klik-luar.
- Quick Generate: auto-open popup saat job `completed`, thumbnail hasil + Unduh, deep link `#/quick-generate?preview=<asset_id>`.
- Popup dipakai ulang di Dashboard filmstrip, Projects & Assets, Campaign Studio, Guided Creation, Remix & Improve, Studio Prompt.
- Tipografi h1/berkas pratinjau pindah ke Newsreader; build hijau, verifikasi CDP + header download.
