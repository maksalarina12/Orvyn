# Orvyn — AI Creative Workspace (local-first)

Orvyn adalah workspace kreatif AI **local-first** untuk Ubuntu: dari brief menjadi gambar, kampanye, storyboard, dan video-assembly — tanpa API berbayar pada jalur utama.

**Status: dalam pengembangan.** Lihat `docs/IMPLEMENTATION_PLAN.md` untuk status nyata per milestone. Jangan berasumsi fitur tersedia sebelum tercantum selesai di sana.

## Ringkasan hardware target (hasil audit)

- Intel i5-8365U, 4C/8T, **tanpa GPU NVIDIA** → inference CPU-only.
- Kelas model yang didukung: SD 1.5-class fp16, resolusi 512, **bukan** SDXL/video generatif.
- Detail: `docs/HARDWARE_ASSESSMENT.md`.

## Menjalankan pengembangan

```bash
scripts/setup.sh     # buat venv + paket backend + frontend deps
scripts/start.sh     # backend di 127.0.0.1:8187, frontend di 127.0.0.1:5170
scripts/test.sh      # pytest backend + build frontend
scripts/stop.sh
```

Dokumen utama: `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/COST_AND_LICENSES.md`.
