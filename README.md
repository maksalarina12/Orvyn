# Orvyn

**A local-first AI creative workspace for turning a brief into images, campaigns, storyboards, and video assemblies — on a CPU-only machine.**

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13-3776AB.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![Tests](https://img.shields.io/badge/backend%20tests-96%20passing-brightgreen.svg)](#testing)

Orvyn is built for creators who want a complete production loop without a cloud account or an expensive GPU. Metadata and generated files stay on your machine; external generation providers are optional, disabled by default, and only used after explicit confirmation.

> **Status:** active development. [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) is the source of truth for what is implemented and verified.

---

## Why Orvyn

- **Local-first by design.** FastAPI binds to `127.0.0.1`, metadata lives in SQLite, assets live on disk.
- **Works without paid APIs.** Free-tier providers and local FFmpeg cover the main workflow. Quotas and provider policies can change; Orvyn reports failures honestly instead of faking progress.
- **CPU-only friendly.** Developed and verified on an Intel i5-8365U with no NVIDIA GPU.
- **End-to-end, not a prompt box.** Projects, guided planning, campaigns, storyboards, workflows, and exports share one asset library.
- **Real media output.** Storyboard animatics are rendered by FFmpeg (H.264/AAC), not simulated.

## Features

| Module | What it does |
|---|---|
| **Dashboard** | Runtime health, recent jobs, output filmstrip, and project overview from real API data. |
| **Quick Generate** | Text-to-image and text-to-video jobs, prompt history, provider selection, automatic provider fallback. |
| **Prompt Studio** | Deterministic prompt builder: structured brief, consistent subject anchors, style/angle variants, copy or generate per variant. |
| **Guided Creation** | Category-aware brief form, deterministic Creative Angle Engine, editable plan, approval into one job per item. |
| **Remix & Improve** | Image-to-image revision flow with server-side source resolution and path-injection protection. |
| **Campaign Studio** | Explicit asset bundling, deterministic typography overlays, ZIP export with `manifest.json` and per-file SHA-256. |
| **Storyboard & Video** | Scene editor, reordering, transitions (cut, fade, wipe, slide, circle), audio track upload, FFmpeg animatic render. |
| **Workflow Center** | Ordered pipelines over verified modules, with retry, skip, reorder, and honest failure states. |
| **Projects & Assets** | Project CRUD, uploads with magic-byte validation, favorites, bulk ZIP download, audio/image/video previews. |
| **Model & Backend** | Enable providers with explicit external-data confirmation, inspect health, manage credentials. |

## Generation providers

All external providers are **disabled by default**. Enabling one requires a confirmation because prompts and assets leave your machine.

| Provider | Modes | Credentials | Notes |
|---|---|---|---|
| `hf_space` | text-to-image | Optional HF token | Hugging Face ZeroGPU Space (FLUX.1-schnell). |
| `hf_space_kontext` | image-to-image | Optional HF token | FLUX.1-Kontext-Dev Space. |
| `hf_space_video` | text-to-video | Optional HF token | ModelScope text-to-video Space. |
| `hf_space_video_ltx` | text-to-video | Optional HF token | LTX-Video distilled, 704×512 output. |
| `pollinations` | text-to-image | None | Keyless Classic API; rate limits apply. |
| `ai_horde` | text-to-image, image-to-image | None (anonymous) or key | Volunteer GPU network; queue times vary. |
| `cloudflare` | text-to-image | Account ID + API token | Workers AI, free daily allowance. |
| `google_ai_studio` | text-to-image, image-to-image | Gemini API key | Free-tier image quota may require billing. |
| `siliconflow` | text-to-image, image-to-image | API key | Free starter credit; model availability may change. |

**Automatic fallback:** if the selected provider fails (quota, rate limit, outage), Orvyn can try another enabled and healthy provider that supports the same mode. The job records the full provider chain. Validation and configuration errors are never retried.

## Architecture

```
┌──────────────────────────┐        HTTP /api        ┌──────────────────────────┐
│  React 18 + TypeScript   │ ──────────────────────> │  FastAPI + Pydantic      │
│  Vite, plain CSS         │ <────────────────────── │  Uvicorn, loopback only  │
└──────────────────────────┘        SSE job events   └────────────┬─────────────┘
                                                                  │
                         ┌────────────────────────────────────────┼────────────────────────┐
                         │                                        │                        │
                 ┌───────▼────────┐                     ┌─────────▼────────┐     ┌─────────▼─────────┐
                 │ SQLite metadata│                     │ Generation queue │     │ FFmpeg media layer│
                 │ data/orvyn.db  │                     │ concurrency = 1  │     │ animatic, audio   │
                 └───────┬────────┘                     └─────────┬────────┘     └─────────┬─────────┘
                         │                                        │                        │
                 ┌───────▼────────┐                     ┌─────────▼────────┐     ┌─────────▼─────────┐
                 │ Files on disk  │                     │ Provider registry│     │ MP4 / overlay /   │
                 │ assets/outputs │                     │ + auto-fallback  │     │ ZIP exports       │
                 └────────────────┘                     └──────────────────┘     └───────────────────┘
```

- **Backend:** Python 3.13, FastAPI, SQLite (stdlib), in-process bounded job queue.
- **Frontend:** React 18, TypeScript, Vite, hand-written CSS (no UI framework).
- **Media:** FFmpeg 8 with structured argument builders; no shell string concatenation.
- **Storage:** SQLite for metadata; relative paths validated against the data root.

## Requirements

- Linux (developed on Ubuntu)
- Python 3.13
- Node.js 18+ and npm
- FFmpeg 8 with `libx264` and AAC support
- ~7 GiB RAM recommended; no NVIDIA GPU required

## Quick start

```bash
git clone https://github.com/maksalarina12/Orvyn.git
cd Orvyn

bash scripts/setup.sh    # create .venv, install backend + frontend dependencies
bash scripts/start.sh    # start backend and frontend
```

Open:

- UI: <http://127.0.0.1:5170>
- API docs: <http://127.0.0.1:8187/docs>
- Health: <http://127.0.0.1:8187/api/health>

Other commands:

```bash
bash scripts/test.sh     # pytest + frontend production build
bash scripts/stop.sh     # stop processes started by start.sh
```

No model weights are downloaded by setup. Providers are configured from **Model & Backend** in the UI.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ORVYN_DATA_DIR` | `./data` | Database, uploads, outputs, cache, exports. |
| `ORVYN_MODELS_DIR` | `./models` | Local model storage (reserved for local fallback). |
| `ORVYN_PORT` | `8187` | Backend port. |
| `ORVYN_HEALTH_DEBUG` | unset | Print provider health-probe timings to the backend log. |

Optional credential fallbacks when a provider config is empty:

`HF_TOKEN`, `GOOGLE_API_KEY`, `CF_API_TOKEN`, `SILICONFLOW_API_KEY`, `AI_HORDE_KEY`.

Credentials entered in the UI are stored locally in `data/orvyn.db`, which is gitignored. Secrets are redacted in API responses.

## Testing

```bash
bash scripts/test.sh
# or
.venv/bin/python -m pytest
cd frontend && npm run build
```

The backend suite covers project/asset CRUD, upload validation, job lifecycle and recovery, provider validation, guided plans, campaigns and overlays, storyboards, FFmpeg renders (including transitions and audio), workflows, prompt studio, and automatic provider fallback. Frontend verification is a full TypeScript production build.

## Project structure

```
backend/
  api/                FastAPI routers
  assets/             Asset metadata, uploads, magic-byte sniffing
  backends/           Provider adapters + registry + fallback selection
  campaigns/          Campaign bundling and overlays
  core/               Config, security, utilities
  creative_planning/  Deterministic angle engine and plans
  database/           SQLite schema and additive migrations
  exports/            ZIP packaging and manifests
  jobs/               Queue, retries, provider fallback
  media/              FFmpeg and PIL media builders
  prompts/            Data-driven prompt builder
  storyboards/        Scenes, transitions, audio, animatic orchestration
  workflows/          Ordered workflow execution
  tests/              pytest suite
frontend/
  src/pages/          Nine workspace modules
  src/components/     Shared UI, preview, command palette
  src/services/       Typed API client
scripts/              setup, start, stop, test
docs/                 Architecture, hardware audit, plans, troubleshooting
data/                 Local runtime data (gitignored)
```

## Privacy and security

- The API binds to loopback by default.
- File paths are stored relative to the data root and validated against path traversal.
- Uploads are checked by magic bytes and size (default limit: 50 MB).
- FFmpeg is invoked with structured argument lists, never a shell command string.
- External providers receive data only after you enable them with explicit confirmation.
- There is no account system, telemetry, or cloud sync.

## Limitations

- This project targets CPU-only machines. Local SDXL and generative video are intentionally out of scope.
- Image generation depends on third-party free tiers; quotas, models, and policies can change without notice.
- Storyboard video is an **animatic** (image + transitions + audio), not generative video.
- Free providers may be rate-limited; fallback improves reliability but cannot guarantee availability.
- The local diffusers SD 1.5 fallback is planned but not installed by default.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Implementation plan and verified status](docs/IMPLEMENTATION_PLAN.md)
- [Hardware assessment](docs/HARDWARE_ASSESSMENT.md)
- [Model catalog and licenses](docs/MODEL_CATALOG.md)
- [Cost and licenses](docs/COST_AND_LICENSES.md)
- [Installation](docs/INSTALLATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Workflows](docs/WORKFLOWS.md)
- [Test report](docs/TEST_REPORT.md)

## Contributing

Issues and pull requests are welcome. Keep changes honest: no placeholder success states, no hidden network calls, and no provider enabled by default. Run `bash scripts/test.sh` before opening a pull request.

## License

Copyright 2026 Orvyn contributors.

Licensed under the [Apache License, Version 2.0](LICENSE). You may use, modify, and distribute this software under the terms of that license. Third-party models and services remain subject to their own licenses and terms.
