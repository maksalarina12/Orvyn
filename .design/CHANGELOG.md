# Changelog Visual

## 27 Okt 2026 — Redesign "Meja Kontrol Darkroom" v0.2

- Ganti seluruh design tokens: warm near-black + amber safelight (sebelumnya: dark blue + ungu #a68df0)
- Font identitas: Archivo + JetBrains Mono (sebelumnya: Inter yang tidak di-load → fallback acak)
- Radius: 3px kontrol / 4px panel (sebelumnya: 8–12px campur)
- Hapus semua bayangan; kedalaman dari layer warna
- Nav bernomor mono (01–09), indikator aktif garis amber kiri; <920px jadi rail atas
- StatusPill → tag persegi mono uppercase; lampu status tetap titik + ring halus
- Label form → micro-label uppercase 10.5px tracking 0.08em
- Prompt readout (base/plan/ps-card) → mono di kotak surface-2
- Brand mark: gradient ungu → blok amber solid + "O" mono hitam
- Aksesibilitas: focus-visible global, prefers-reduced-motion, kontras diverifikasi (§AUDIT)
- Sumber kebenaran: `.design/DESIGN.md`

## 27 Okt 2026 — Pass 2: "Instrument Board"

- Shell baru: **top rail telemetri** (sticky) — path mono `ORVYN / <halaman>`, lampu nyata DB · FFMPEG · INFER, rasio provider siap/aktif, versi app
- Status backend pindah dari sidebar ke top rail; sidebar kini murni navigasi + footer `LOCAL-FIRST · SQLITE · FFMPEG`
- Dashboard direstruktur jadi papan instrumen: header berkicker mono, grid 2 kolom (SYSTEM CHECK / MULAI KERJA), lalu **JOB TERAKHIR** (log readout nyata dari /api/generations), **OUTPUT TERBARU** (filmstrip horizontal aset nyata), **PROYEK**
- Komponen baru: `.sec-head` (index mono + judul uppercase + hairline rule), `.readout-row` (label/nilai mono), `.quick-grid` (shortcut bernomor), `.job-row` (grid telemetri), `.filmstrip/.film-frame` (strip 4:3 dengan caption mono + hash ID)
- Skala tipografi: h1 20px → 25px, kicker mono 10px tracking 0.14em
- Mobile: rail labels disembunyikan, footer sidebar hilang, job-row jadi 3 kolom

## 27 Okt 2026 — Pass 3: "Studio Cetak" (redesign total)

- Arah visual diganti sepenuhnya: tema terang editorial (kertas #f1ebdd, tinta #161410, aksen merah sinyal #b23a22). Tema darkroom amber dihapus.
- Tipografi baru: **Newsreader** (display serif) + **IBM Plex Sans** (body) + **IBM Plex Mono** (data). Archivo/JetBrains Mono dihapus dari `index.html`.
- Sidebar dihapus → **masthead** dua baris: monogram + wordmark serif + telemetri nyata, lalu nav 9 modul bernomor dengan garis aktif merah. Komponen `Masthead.tsx` menggantikan `Sidebar.tsx` + `TopRail.tsx`.
- `styles.css` ditulis ulang total (token, shell, panel, form, tombol, tabel, aset, scene, prompt studio, responsif).
- Panel tanpa kotak: pemisah berupa aturan garis 2px tinta; kartu hanya untuk proyek/aset/scene.
- Tombol/label/pill jadi persegi (radius 0–2px), mono uppercase.
- Perbaikan hasil QA screenshot: nav 9 item muat di 1180px, underline aktif terlihat, tombol disabled tidak lagi blok abu-abu, tombol simpan kredensial tidak melar, label provider disembunyikan di ≤560px agar tidak terpotong.

## 27 Okt 2026 — Pass 4: "Werkstatt" (fokus kecepatan kerja)

- Arah visual baru: netral dingin (bg `#edf0f4`, surface putih, cobalt `#2b46f0`), Instrument Sans + JetBrains Mono. Tema editorial kertas/serif dihapus.
- Shell baru `Shell.tsx`: rail navigasi kiri yang bisa diciutkan (localStorage), topbar sticky (breadcrumb, cari, lampu runtime, bantuan), bottom nav 5 tujuan di mobile.
- **Command palette** (`Ctrl/⌘+K`) dengan pencarian, navigasi keyboard, aksi rail, dan dialog pintasan (`?`).
- Pintasan global: `1–9` lompat halaman, `⌘⏎` kirim job, `Esc` tutup; abaikan saat mengetik/dialog.
- Quick Generate: riwayat prompt lokal 8 entri (chip klik-untuk-pakai, tombol hapus) + hint `⌘⏎`.
- Densitas dinaikkan: kontrol 32px, panel 14/16px, tabel rapat, konten maks 1280px.
- Responsif: rail otomatis ciut ≤1080px; ≤760px rail hilang → bottom nav + padding aman `env(safe-area-inset-bottom)` + `viewport-fit=cover`.
- Diverifikasi lewat CDP: palette terbuka, filter "proj" + Enter → `#/projects`, tombol `2` → `#/quick-generate`, `?` membuka daftar pintasan.

### 4.1 — Scroll & scrollbar (27 Okt 2026)

- Semua scrollbar disembunyikan (global, termasuk rail/filmstrip/palette) tanpa menghilangkan scroll.
- `useSmoothScroll`: wheel halaman di-ease (kecepatan 0.62, easing 0.085) sehingga terasa lebih lambat dan halus; kontainer dalam tetap native.
- Palette terbuka → scroll halaman dikunci; daftar palette tetap bisa di-scroll.
- Mobile/touch dan `prefers-reduced-motion` tetap memakai scroll native.
- Diuji via CDP: scrollbar 0px, wheel 300 → 186 (127 pada 200ms), kembali ke 0; palette list scroll 68px tanpa menggeser halaman.

### 4.2 — Palet hangat + collapse rail (27 Okt 2026)

- Palet kembali ke warna hangat yang disukai: kertas `#f1ebdd`, surface `#fbf7ed`, tinta `#161410`, aksen merah `#b23a22`; wash/hatch/shadow disesuaikan. Struktur Werkstatt (rail, palette, densitas) tetap.
- Collapse rail: tombol «/» diperbesar, pintasan `⌘B`/`Ctrl+B`, `aria-expanded`, status tersimpan; footer rail disembunyikan saat ciut agar tidak menyisakan titik tanpa konteks.
- Kontras dihitung ulang: aktif merah 4.84:1 di wash, muted 5.0:1, ok 6.0, warn 5.6, fail 5.1.
- Teruji CDP: rail 224 → 60 → 224, state "collapsed" tersimpan.


### 4.3 — Pratinjau popup + Unduh (27 Okt 2026)

- `AssetPreview.tsx`: popup pratinjau hasil dengan stage media gelap, metadata asli (dimensi/ukuran/mime/provider), prompt + salin, tombol **Unduh** (nama file dari `Content-Disposition` backend), tautan Projects, Esc/klik-luar.
- Quick Generate: popup terbuka otomatis saat job selesai; thumbnail hasil + tombol Unduh; deep link `?preview=<asset_id>`.
- Popup yang sama dipakai di Dashboard (filmstrip), Projects & Assets, Campaign Studio, Guided Creation, Remix & Improve, Studio Prompt — klik aset tidak lagi membuka tab baru.
- Tipografi: h1 + nama file pratinjau memakai Newsreader (display), body tetap Instrument Sans; skala h1 30–31px.
- QA: build hijau; deep link + Esc membersihkan query; `Content-Disposition: attachment; filename="…"` terverifikasi; screenshot popup gambar & video.
