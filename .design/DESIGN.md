# Konvensi Visual: "Werkstatt"

Sumber kebenaran tampilan Orvyn. Setiap perubahan UI harus lolos daftar ini.

## 1. Tesis

Orvyn adalah **meja kerja (Werkstatt)** untuk AI designer: netral, padat, dan cepat. Bukan poster, bukan dashboard dekoratif. Semua ruang dipakai untuk kerja: navigasi tetap di rail kiri, aksi global di command palette, data dalam tabel rapat, dan setiap layar punya satu jalur cepat ke pekerjaan berikutnya.

Kata kunci: netral, padat, presisi, cepat, tanpa hiasan.

## 2. Palet (`:root` di styles.css)

| Token | Nilai | Pakai |
|---|---|---|
| `--bg` | `#f1ebdd` | latar aplikasi (kertas hangat) |
| `--surface` | `#fbf7ed` | panel, rail, input |
| `--surface-2` | `#f5efe2` | bidang sekunder, chip, kode |
| `--surface-3` | `#eae3d2` | field group, tag netral |
| `--ink` | `#161410` | teks utama |
| `--ink-2` | `#332e24` | teks sekunder |
| `--muted` | `#6b6352` | metadata (5.0:1 di atas bg) |
| `--line` / `--line-2` | `#d8ceba` / `#b3a78d` | border 1px |
| `--accent` | `#b23a22` | aksi, navigasi aktif, fokus (4.8:1 di atas wash) |
| `--accent-wash` | `#f6e4dc` | latar item aktif |
| `--ok/warn/fail` | `#2c6247` / `#7f5314` / `#a93a28` | status + wash hangat |

Aturan: aksen merah hanya untuk aksi/aktif/fokus. Status memakai wash + border tipis, bukan warna teks saja.

## 3. Tipografi

- UI/body: **Instrument Sans** 13px / 1.5. Judul panel 600 weight, tracking negatif ringan.
- Display h1 + nama berkas pratinjau: **Newsreader** 500 (satu-satunya serif; memberi karakter "ledger studio" tanpa dekorasi).
- Data/label: **JetBrains Mono** — label form 9px uppercase tracking 0.08em, nilai teknis 9.5–11.5px tabular.
- Skala: h1 30–31px (24px mobile), h2 14–15px, h3 13–13.5px, body 13px, small 11.5px.
- Dilarang: serif selain Newsreader, font script/rounded, heading raksasa, huruf mono untuk paragraf.

## 4. Shell & densitas

- **Rail kiri** 224px (ciut 60px, tombol «/», `⌘B`/`Ctrl+B`, tersimpan di localStorage; footer status disembunyikan saat ciut). Di ≤1080px otomatis 60px; ≤760px rail hilang dan diganti **bottom nav** 5 tujuan (Home, Quick, Library, Flow, Models).
- **Topbar** 46px sticky: breadcrumb mono, tombol cari (⌘K), lampu DB/FFmpeg/Infer, tombol `?`.
- Konten maks 1280px, padding 22/24px (mobile 16/14 + ruang bottom nav).
- Jarak vertikal rapat: page gap 18px, panel padding 14/16px, kontrol tinggi 32px.

## 5. Pintasan kerja (wajib dipertahankan)

- `⌘K / Ctrl K` — command palette: cari halaman, aksi rail, daftar pintasan.
- `1–9` — lompat halaman sesuai nomor rail (diabaikan saat mengetik/di dialog).
- `⌘⏎ / Ctrl ⏎` — kirim job dari prompt Quick Generate.
- `?` — dialog pintasan; `Esc` menutup.
- Prompt Quick Generate punya riwayat lokal 8 entri (klik chip untuk memakai ulang).

## 5b. Pratinjau hasil (wajib)

Semua klik aset membuka **popup pratinjau**, bukan tab baru atau pindah halaman. Popup: backdrop gelap hangat, panel surface radius 8, stage media gelap (gambar `contain` / video kontrol autoplay), metadata nyata (dimensi, ukuran, mime, provider), prompt + salin, tombol **Unduh** (memakai `Content-Disposition` asli dari backend), tautan Projects, dan penutup Esc/klik-luar/tombol. Setelah job selesai, popup hasil pertama terbuka otomatis. Deep link `#/quick-generate?preview=<asset_id>` membuka popup yang sama dan dibersihkan saat ditutup.
- Berlaku di Dashboard (filmstrip), Projects & Assets, Campaign Studio, Guided Creation, Remix & Improve, Quick Generate, dan Studio Prompt.

## 6. Komponen

- **Panel**: surface putih, border 1px `--line`, radius 6px, padding 14/16. Header 14px 600 + aksi kanan.
- **Section head**: indeks mono cobalt 9.5px + judul 10.5px uppercase 600 + garis pengisi.
- **Tombol**: tinggi 32 (26 small), radius 4, 12px 500, bukan uppercase. Primary cobalt; sekunder putih + border; danger merah wash.
- **Input**: tinggi 32, radius 4, border `--line-2`; fokus border cobalt + ring `--accent-wash`.
- **Pill status**: mono 9px uppercase, radius 3, wash + border sesuai tone.
- **Baris data**: tinggi 30–34px, hairline `--line`, angka tabular, kolom tetap.
- **Kartu aset/proyek**: radius 4–6, border hairline, caption mono 9px.
- **Palette**: dialog 560px, item 36px, aktif `--accent-wash` + teks cobalt, footer pintasan mono.

## 7. Gerak & scroll

Transisi 100–140ms hanya pada warna/border/lebar rail. Tanpa animasi masuk, parallax, atau glow.

Scroll halaman memakai glide kustom: roda mouse tidak melompat, melainkan di-ease ke target (`deltaY × 0.62`, easing 0.085 per frame). Scrollbar disembunyikan di semua elemen (`scrollbar-width: none`, `::-webkit-scrollbar { display: none }`) tanpa mematikan kemampuan scroll. Kontainer dalam (rail, filmstrip, daftar palette, prompt) tetap memakai scroll native dan tidak dibajak; saat palette terbuka, halaman di belakang dikunci. Perangkat sentuh (`pointer: coarse`) dan `prefers-reduced-motion` memakai scroll native.

## 8. Anti-pattern terblokir

- Tema gelap, ungu/indigo (selain cobalt fungsional), gradient dekoratif, glassmorphism, blur, glow.
- Kartu membulat besar, chip pastel, ilustrasi 3D generik, emoji ikon.
- Whitespace berlebihan, heading dekoratif, teks mono untuk paragraf.
- Data/metrik palsu; semua telemetri dari API nyata.
- Dialog tanpa jalur Esc/klik-luar.

## 9. Aksesibilitas

- Kontras ≥4.5:1 untuk teks (muted 5.0:1, accent 4.84:1 di wash).
- Fokus terlihat: outline 2px accent (input memakai ring wash + border accent).
- Target sentuh bottom nav ≥42px; tombol ≥26px; label selalu ada di samping status warna.
- Semua pintasan punya padanan klik (tombol cari, tombol `?`, chip riwayat).
