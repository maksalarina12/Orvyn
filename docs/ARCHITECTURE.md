# Architecture — Orvyn

## Prinsip pemilihan arsitektur

Dipilih berdasarkan hasil audit hardware (lihat `HARDWARE_ASSESSMENT.md`), bukan preferensi. Target: laptop CPU-only 7 GiB RAM. Aturan: dependency sekecil dan semurah mungkin; modul terpisah; semua operasi lokal; bind loopback.

## Stack (keputusan tetap untuk v1)

| Lapisan | Teknologi | Alasan |
|---|---|---|
| Backend API | Python 3.13 + FastAPI + Uvicorn | Ringan, async, validasi Pydantic |
| Database | SQLite (file `data/orvyn.db`) | Zero-dependency, cukup untuk metadata lokal |
| Large files | Filesystem `data/assets/`, `data/outputs/` | DB hanya metadata + path validasi |
| Job queue | In-process bounded queue + subprocess worker inference | Cukup untuk concurrency 1; model dijadikan worker subprocess terisolasi agar API tetap responsif |
| Image inference | Generation Gateway: 1) HF ZeroGPU Spaces via Gradio API (opsional, disabled by default, konfirmasi eksternal), 2) fallback lokal diffusers CPU SD1.5 fp16 (rancangan) | Hardware ini CPU-only; komputasi gratis berkuota memberi kecepatan nyaman, lokal menjamin ketersediaan Rp0 |
| Media processing | FFmpeg (terpasang, v8.0.1) | Animatic video, title card, audio, export |
| Frontend | React 18 + TypeScript + Vite, CSS murni (tanpa Tailwind) | Shelly + kontrol penuh; tanpa tooling ekstra |
| Test | pytest (backend), vite build + smoke test (frontend) | |

## Struktur modul backend

```
backend/
  api/               FastAPI routers (health, projects, assets, jobs, models, ...)
  core/              config (paths, settings), logging, security helpers
  database/          sqlite connection, migrations, repositories
  projects/          project CRUD domain logic
  assets/            asset metadata, file registration, path validation
  prompts/           prompt builder + template registry (data-driven)
  creative_planning/ Creative Angle Engine + concept generation (deterministik dulu)
  campaigns/         campaign brief, plan, asset planning, overlay text
  storyboards/       scene editor + animatic assembly orchestration
  workflows/         workflow definitions, dependency steps, approval checkpoints
  jobs/              queue, state machine (queued/running/completed/failed/cancelled)
  backends/          BackendAdapter interface + DiffusersBackend + (nanti) ComfyUI/OpenVINO
  media/             FFmpeg wrappers (probe, sanitasi, assembly)
  exports/           export package + manifest
  tests/             pytest backend tests
```

## Keamanan data

- Semua path file disimpan **relatif terhadap root data dir**, divalidasi dengan resolusi + cek `commonpath` — anti path-traversal.
- Upload: validasi magic bytes untuk gambar, batas ukuran default 50 MB.
- API tidak mengeksekusi shell yang dibangun dari output model; FFmpeg dipanggil lewat builder argumen terstruktur, bukan string concat.
- Server bind `127.0.0.1` oleh default. Port default: 8187 (hindari bentrok ComfyUI 8188).

## Job lifecycle

`queued → running → completed | failed | cancelled`
- Retry dibatasi (default: max 2 attempts) hanya untuk kelas error eligible (mis. timeout worker); error validasi tidak di-retry.
- Semua state disimpan di DB; frontend membaca state nyata, tidak ada progress fiktif. Progress dari worker dipetakan langkah-per-langkah (jika backend mendukung) atau indeterminate.
- Hasil generation tersimpan di `data/outputs/<project-slug>/<job-id>/` dengan metadata lengkap.

## Frontend

- Shell persisten: sidebar navigasi 9 modul + konten.
- State dari API nyata (health, models, jobs). Skeleton loading, empty state nyata, banner "backend unavailable" dengan pesan actionable.
- Bahasa UI: bisa campur; teks teknis ikut terminologi Inggris.

## API v1 (awal)

- `GET /api/health` — status runtime, sqlite, ffmpeg, backend, disk, RAM (dipakai Dashboard).
- `GET/POST/PATCH/DELETE /api/projects` (+ `GET /api/projects/{id}`)
- `GET/POST /api/assets` (+ per project), `GET /api/assets/{id}/file`
- `POST /api/jobs` (generate), `GET /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`
- `GET /api/backends/status`, `GET /api/models`, (Milestones berikutnya: install/catalog/download)
- Detail akan diupdate per milestone; router di `backend/api/`.
