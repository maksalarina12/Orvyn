# Referensi — sintesis 27 Okt 2026

## REFERENCE — Darkroom (darkroom.co)
- URL: https://darkroom.co · Apple Design Award, 20M+ downloads
- Kategori: editor foto/video (kategori terdekat dengan Orvyn)
- Why relevant: produk foto-first; UI harus tidak bersaing dengan gambar
- TYPOGRAPHY: label kontrol 11px tenang, high contrast tapi tidak dominan
- COLOR: canvas near-black rgb(17,17,17); foto = elemen paling terang
- LAYOUT: split viewer/tools; konten dulu, kontrol kemudian
- MOTION: minim; Liquid Glass baru (iOS 26) — tidak relevan untuk web tool
- What to borrow: near-black neutral, gambar paling terang, label kecil tenang, filosofi non-destruktif ("job bisa dibatalkan, error jujur")
- What NOT to copy: translucency/glass, layout mobile split

## REFERENCE — Mission Control / amber telemetry (NASA/JPL/SpaceX readouts)
- URL: https://opendesigner.io/fr/design-systems/mission-control · https://theme.chakri.me
- Kategori: command-center/telemetry UI
- Why relevant: Orvyn = panel kendali job/provider/kuota — telemetri nyata
- TYPOGRAPHY: mono presisi (JetBrains Mono), uppercase micro-labels dengan tracking, tabular numerals
- COLOR: amber data di atas near-black; hijau/merah hanya untuk status fungsional
- LAYOUT: dense panels, hairline border, radius kecil (4px)
- COMPONENTS: lampu indikator, chip status, readout mono
- What to borrow: satu aksen amber untuk interaksi, mono untuk ID/angka, lampu status, hairline, radius 3-4px
- What NOT to copy: CRT glow, scanline, dot-matrix, estetika retro berlebihan

## REFERENCE — Palantir-style product UI (Foundry/Gotham register)
- URL: https://github.com/Ax1i1om/palantir-design (analisis komunitas)
- Why relevant: operator console untuk data kerja, bukan marketing site
- TYPOGRAPHY: body 13px/1.45 — kepadatan kerja
- LAYOUT: grid 4px, panel sebagai plane, monokrom + warna fungsional saja
- What to borrow: radius 4px square controls, 4px spacing, warna hanya fungsional
- What NOT to copy: three-pane shell berat, data grid sebagai hero (belum relevan untuk Orvyn)

## Anti-referensi (dilihat, dihindari)
- SCADA dashboard glassmorphism + neon blue glow (tahaprime/ioTdashboard) — slop: glow, blur, gradient background, chart dekoratif tanpa data analitik.

## SINTESIS (arah final Orvyn)
- typography: Archivo (UI/display) + JetBrains Mono (data) — bukan Inter
- palette: warm near-black (#121110–#2b2721) + amber safelight #eda63e hanya untuk interaksi/fokus/indikator aktif; status ok hijau desaturasi / merah hangat
- composition: sidebar instrumen bernomor (01–09, mono), konten 1120px, panel hairline flat
- density: body 13px, panel 16/18, list 10px — kerja, bukan pameran
- interaction: fokus amber ring, hover = naik satu layer warna (bukan shadow), transisi 120ms warna saja
- imagery: thumbnail aset = elemen paling terang (darkroom rule)
- signature: mono readout (prompt/ID), nomor urut, lampu status, blok amber solid pada primary action (satu-satunya permukaan amber terang)
