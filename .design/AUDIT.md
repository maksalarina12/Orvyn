# Audit Visual — Orvyn

Terakhir: 27 Okt 2026 (redesign "Meja Kontrol Darkroom").

## QA findings

- [x] Thesis jelas: meja kontrol darkroom — amber safelight + mono telemetri + hairline; bukan SaaS template
- [x] Tidak ada gradient dekoratif (brand-mark gradient lama diganti blok amber solid + mono "O")
- [x] Tidak ada shadow/blur/glow; kedalaman dari layer warna
- [x] Radius sistematis: 3px kontrol, 4px panel; pill status persegi 2px; lampu titik tetap bulat (indikator)
- [x] Font exact: Archivo + JetBrains Mono dengan fallback offline (Google Fonts bisa gagal → layout tetap)
- [x] Amber hanya di: brand mark, nav aktif, fokus, tombol primary, panel-head marker, wf-step-num — tidak di teks biasa
- [x] Kontras: teks 13:1, muted 5.4:1, amber 8.9:1, teks di tombol primary 8.9:1
- [x] focus-visible global 2px amber; prefers-reduced-motion mematikan transisi
- [x] Responsive <920px: sidebar jadi rail atas horizontal (nomor disembunyikan), konten padding 16px
- [x] StatusPill jadi tag mono uppercase persegi (bukan pill bulat)
- [x] Anti-pattern terblokir di .design/DESIGN.md §7

## Kelemahan yang diketahui (belum dikerjakan)

- Font Google di-load via CDN — offline pertama kali tanpa cache = fallback system. Solusi ideal: self-host WOFF2 di /public.
- Chart/grafik tidak ada (belum dibutuhkan); kalau nanti ada, harus telemetri nyata dari job engine, bukan dekorasi.
- Screenshot otomatis belum ada di repo; QA saat ini manual via kode + build. Perlu mode komponen terisolasi bila UI bertambah besar.

## Pass 2 QA — "Instrument Board"

- [x] Hierarki halaman jelas: kicker mono → h1 25px → deskripsi → hairline; tidak ada h1 raksasa/dekoratif
- [x] Top rail memakai data nyata (health + providers); tidak ada angka karangan atau grafik dekoratif
- [x] Amber tetap terbatas: penanda index section, path halaman, hover border, tombol primary
- [x] Semua nilai teknis (ID job, dimensi, provider, versi) memakai JetBrains Mono tabular
- [x] Filmstrip: frame 4:3 konsisten, caption mono, placeholder video berupa hatch (fungsional)
- [x] Job log punya keadaan nyata: queued/running/completed/failed/cancelled dipetakan ke tone lamp
- [x] Mobile: rail label disembunyikan (label provider tetap), job-row 3 kolom, quick-grid 1 kolom di <520px
- [x] Tidak ada shadow/glass; sticky rail memakai bg solid 92% + hairline (tanpa blur)
- [x] Tombol/link tetap punya target ≥24px; fokus amber 2px terjaga

## Pass 3 QA — "Studio Cetak" (screenshot Chrome headless 1440×1000 & 390×844)

- [x] Dashboard, Quick Generate, Guided Creation, Projects & Assets, Workflow Center, Model & Backend diperiksa visual nyata
- [x] Tesis terbaca: kertas + tinta + serif + garis + indeks merah; tidak ada sisa tema gelap/amber
- [x] Kontras dihitung: muted 5.0, merah 5.0, ok 6.0, warn 5.6, fail 5.3 (semua ≥4.5 di atas paper)
- [x] Nav 9 item muat tanpa terpotong; item aktif punya garis merah di atas border tinta masthead
- [x] Mobile 390px: masthead rapi, label telemetri disembunyikan, nav bisa di-scroll, form 1 kolom
- [x] Job log rata kolom (pill 88px), provider panjang di-truncate
- [x] Kartu provider: tombol tidak lagi melar mengikuti grid; input rata bawah
- [x] Disabled button: garis abu + teks muted, bukan blok abu gelap
- [x] Tidak ada shadow/glow/gradient dekoratif; hatch hanya untuk placeholder video
- [ ] Screenshot halaman Campaign Studio, Storyboard & Video, Remix & Improve belum diambil (struktur kelas sama, risiko rendah)

## Pass 4 QA — "Werkstatt" (1440×1000, 390×844, CDP)

- [x] Dashboard, Quick Generate, palette, dialog pintasan diperiksa screenshot
- [x] Kontras: muted 5.0:1, cobalt 6.9:1, ok 5.1:1, warn 5.6:1, fail 6.2:1 (dihitung)
- [x] Densitas konsisten: kontrol 32px, baris tabel ~30px, panel 14/16px
- [x] Rail ciut/lebar tersimpan setelah reload; status rail menyatu di footer
- [x] Mobile 390px: rail hilang, bottom nav 5 item aktif, topbar tetap, konten tidak tertutup
- [x] Command palette teruji fungsional (buka, filter, Enter, Esc) via Chrome DevTools Protocol
- [x] Pintasan angka & `?` teruji; tidak mencuri input saat fokus di field/dialog
- [x] Tidak ada shadow kecuali dialog palette; tanpa blur/glow/gradient dekoratif
- [x] Kartu aset/proyek memakai hairline + radius kecil; target sentuh ≥42px di bottom nav
- [ ] Halaman Campaign/Storyboard/Remix belum di-screenshot pass ini (kelas komponen sama)

## Pass 4.1 QA — scroll

- [x] `window.innerWidth - clientWidth = 0` (scrollbar tidak memakan ruang)
- [x] Wheel 300px: posisi 200ms = 127, settle = 186 (glide, bukan lompat)
- [x] Wheel balik −300 → kembali 0
- [x] Palette list scroll native (68px) sementara halaman di belakang tetap 0
- [x] Touch device & reduced-motion tidak memakai hijack wheel


## Pass 4.3 QA — pratinjau popup

- [x] Popup gambar 512×512 tampil di tengah, stage gelap, metadata (44 KB, image/webp) benar
- [x] Popup video memutar `ltx_out.mp4` dengan kontrol; ukuran 34 KB terbaca
- [x] Esc menutup popup dan menghapus `?preview=` dari hash (CDP: `open:false`, `#/quick-generate`)
- [x] `GET /api/assets/<id>/file` → `content-disposition: attachment; filename="…"` (Unduh benar)
- [x] Klik aset di Dashboard/Projects/Campaign/Guided/Remix membuka popup yang sama (build lolos tipe)
- [x] Newsreader hanya di h1/berkas; kontras mengikuti token lama
- [ ] Auto-open setelah generation belum diuji ulang dengan job nyata (kuota ZeroGPU habis)
