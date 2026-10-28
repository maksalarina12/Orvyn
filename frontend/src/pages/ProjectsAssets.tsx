import { useMemo, useState } from "react";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { EmptyState, StatusPill } from "../components/ui";
import { AssetPreview } from "../components/AssetPreview";
import { downloadZip } from "../lib/download";
import type { Asset, Project } from "../types/api";

const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "general", label: "General Creative Work" },
  { value: "product_advertisement", label: "Product Advertisement" },
  { value: "brand_identity", label: "Brand Identity" },
  { value: "social_media", label: "Social Media Content" },
  { value: "music_promotion", label: "Music Promotion" },
  { value: "album_artwork", label: "Album & Single Artwork" },
  { value: "ecommerce", label: "E-commerce Graphics" },
  { value: "editorial_poster", label: "Editorial & Poster" },
  { value: "concept_art", label: "Concept Art" },
  { value: "cinematic_scene", label: "Cinematic Scene" },
  { value: "video_advertisement", label: "Video Advertisement" },
];

export function ProjectsAssets() {
  const [reloadKey, setReloadKey] = useState(0);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [assetKey, setAssetKey] = useState(0);
  const projects = useApiState<{ items: Project[] }>(() => api.projects({}), [reloadKey]);
  const assets = useApiState<{ items: Asset[] }>(() => api.assets({ limit: 60 }), [assetKey]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("general");
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "image" | "video" | "favorite">("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [favorites, setFavorites] = useState<Record<string, boolean>>({});
  const [bulkBusy, setBulkBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = () => {
    setReloadKey((k) => k + 1);
    setAssetKey((k) => k + 1);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createProject({ name: name.trim(), category });
      setCreating(false);
      setName("");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat proyek");
    }
  };

  const remove = async (p: Project) => {
    if (
      !window.confirm(
        `Hapus proyek "${p.name}"? Aset tidak ikut dihapus, hanya terlepas dari proyek ini.`
      )
    )
      return;
    try {
      await api.deleteProject(p.id);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus proyek");
    }
  };

  const moveAsset = async (asset: Asset, projectId: string) => {
    try {
      await api.updateAsset(asset.id, { project_id: projectId });
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memindahkan aset");
    }
  };

  const isFavorite = (asset: Asset) => favorites[asset.id] ?? asset.is_favorite;
  const filtered = useMemo(() => {
    const items = assets.data?.items ?? [];
    if (filter === "image") return items.filter((a) => a.file_type === "image");
    if (filter === "video") return items.filter((a) => a.file_type === "video");
    if (filter === "favorite") return items.filter((a) => favorites[a.id] ?? a.is_favorite);
    return items;
  }, [assets.data, filter, favorites]);
  const allSelected = filtered.length > 0 && filtered.every((a) => selected.has(a.id));

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (allSelected) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(filtered.map((a) => a.id)));
  };

  const toggleFavorite = async (asset: Asset) => {
    const next = !isFavorite(asset);
    setFavorites((prev) => ({ ...prev, [asset.id]: next }));
    try {
      await api.updateAsset(asset.id, { is_favorite: next });
    } catch (err) {
      setFavorites((prev) => ({ ...prev, [asset.id]: !next }));
      setError(err instanceof Error ? err.message : "Gagal mengubah favorit");
    }
  };

  const downloadSelected = async () => {
    if (selected.size === 0) return;
    setBulkBusy(true);
    setError(null);
    try {
      await downloadZip([...selected]);
      setNotice(`${selected.size} aset diunduh sebagai zip.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengunduh zip");
    } finally {
      setBulkBusy(false);
    }
  };

  const deleteSelected = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Hapus ${selected.size} aset? File di disk juga dihapus dan tidak bisa dikembalikan.`)) return;
    setBulkBusy(true);
    setError(null);
    try {
      await Promise.all([...selected].map((id) => api.deleteAsset(id)));
      setNotice(`${selected.size} aset dihapus.`);
      setSelected(new Set());
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus aset");
    } finally {
      setBulkBusy(false);
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Projects &amp; Assets</h1>
          <p>Proyek tersimpan di SQLite lokal; file aset di folder data/.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating((c) => !c)}>
          {creating ? "Tutup" : "+ Proyek baru"}
        </button>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {creating ? (
        <form className="panel create-form" onSubmit={submit}>
          <label>
            Nama proyek
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="mis. Launch Campaign Kopi"
            />
          </label>
          <label>
            Kategori
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn-primary" type="submit">
            Buat proyek
          </button>
        </form>
      ) : null}

      {projects.loading ? (
        <div className="page-loading">Loading…</div>
      ) : projects.data && projects.data.items.length > 0 ? (
        <div className="grid-cards">
          {projects.data.items.map((p) => (
            <article key={p.id} className="project-card">
              <h3>{p.name}</h3>
              <p className="muted small">{p.description || "Tidak ada deskripsi."}</p>
              <div className="project-meta">
                <StatusPill tone="neutral">{p.category.replace(/_/g, " ")}</StatusPill>
                <StatusPill tone="neutral">{p.asset_count} aset</StatusPill>
              </div>
              <p className="muted small">
                Dibuat {new Date(p.created_at).toLocaleString("id-ID")}, diubah{" "}
                {new Date(p.updated_at).toLocaleString("id-ID")}
              </p>
              <button className="btn btn-danger" onClick={() => remove(p)}>
                Hapus
              </button>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Belum ada proyek"
          detail="Proyek menyimpan brief, aset, dan hasil generation."
        />
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>Aset terbaru</h2>
          <span className="muted small">Hasil generation tanpa project tampil sebagai “unassigned”.</span>
        </div>
        <div className="asset-toolbar">
          <div className="seg" role="group" aria-label="Filter aset">
            {(
              [
                ["all", "Semua"],
                ["image", "Gambar"],
                ["video", "Video"],
                ["favorite", "Favorit"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={filter === value ? "seg-btn is-active" : "seg-btn"}
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <span className="muted small">
            {filtered.length} / {assets.data?.items.length ?? 0} aset
          </span>
          <div className="asset-toolbar-right">
            <button type="button" className="btn btn-small" onClick={selectAll}>
              {allSelected ? "Batal pilih" : "Pilih semua"}
            </button>
            {selected.size > 0 ? (
              <>
                <button type="button" className="btn btn-small" onClick={downloadSelected} disabled={bulkBusy}>
                  {bulkBusy ? "Memproses…" : `Unduh zip (${selected.size})`}
                </button>
                <button type="button" className="btn btn-small btn-danger" onClick={deleteSelected} disabled={bulkBusy}>
                  Hapus
                </button>
              </>
            ) : null}
          </div>
        </div>
        {notice ? <div className="notice-line">{notice}</div> : null}
        {assets.loading ? (
          <div className="page-loading">Loading…</div>
        ) : assets.data && assets.data.items.length > 0 && filtered.length > 0 ? (
          <div className="asset-grid">
            {filtered.map((asset) => (
              <figure
                key={asset.id}
                className={`asset-card asset-card-managed${selected.has(asset.id) ? " is-selected" : ""}`}
              >
                <div className="asset-select">
                  <input
                    type="checkbox"
                    checked={selected.has(asset.id)}
                    onChange={() => toggleSelect(asset.id)}
                    aria-label={`Pilih ${asset.filename}`}
                  />
                  <button
                    type="button"
                    className={isFavorite(asset) ? "fav-btn is-on" : "fav-btn"}
                    onClick={() => toggleFavorite(asset)}
                    title={isFavorite(asset) ? "Hapus dari favorit" : "Tandai favorit"}
                    aria-label={isFavorite(asset) ? "Hapus dari favorit" : "Tandai favorit"}
                  >
                    {isFavorite(asset) ? "★" : "☆"}
                  </button>
                </div>
                <button
                  type="button"
                  className="asset-open"
                  onClick={() => setPreviewId(asset.id)}
                  title={`Pratinjau ${asset.filename}`}
                >
                  {asset.file_type === "image" ? (
                    <img src={assetFileUrl(asset.id)} alt={asset.filename} loading="lazy" />
                  ) : (
                    <span className="film-video">▶ VIDEO</span>
                  )}
                  <span className="asset-open-hint">Pratinjau</span>
                </button>
                <figcaption>
                  <div className="flex-between">
                    <span className="asset-name" title={asset.filename}>
                      {asset.filename}
                    </span>
                    {asset.project_id ? null : <StatusPill tone="warn">unassigned</StatusPill>}
                  </div>
                  <select
                    className="asset-move"
                    value={asset.project_id ?? ""}
                    onChange={(e) => moveAsset(asset, e.target.value)}
                    aria-label="Pindahkan aset ke project"
                  >
                    <option value="">— unassigned —</option>
                    {(projects.data?.items ?? []).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </figcaption>
              </figure>
            ))}
          </div>
        ) : assets.data && assets.data.items.length > 0 ? (
          <div className="asset-filter-empty">
            Tidak ada aset untuk filter ini.{" "}
            <button type="button" className="linkish" onClick={() => setFilter("all")}>
              Tampilkan semua
            </button>
          </div>
        ) : (
          <EmptyState
            title="Belum ada aset"
            detail="Upload aset atau jalankan generation; hasilnya muncul di sini."
          />
        )}
      </section>
      {previewId ? <AssetPreview assetId={previewId} onClose={() => setPreviewId(null)} /> : null}
    </div>
  );
}
