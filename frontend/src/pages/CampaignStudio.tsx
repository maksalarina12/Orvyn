import { useState } from "react";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { EmptyState, StatusPill } from "../components/ui";
import { AssetPreview } from "../components/AssetPreview";
import type { Asset, Campaign, Project } from "../types/api";

const STATUS_TONES: Record<string, "ok" | "warn" | "neutral"> = {
  draft: "neutral",
  active: "warn",
  completed: "ok",
};

export function CampaignStudio() {
  const projects = useApiState<{ items: Project[] }>(() => api.projects({}), []);
  const allAssets = useApiState<{ items: Asset[] }>(() => api.assets({ limit: 100 }), []);
  const [listKey, setListKey] = useState(0);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const campaigns = useApiState<{ items: Campaign[] }>(() => api.campaigns({}), [listKey]);
  const [open, setOpen] = useState<Campaign | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [projectId, setProjectId] = useState("");
  const [pickAsset, setPickAsset] = useState("");
  const [overlayAsset, setOverlayAsset] = useState("");
  const [overlayText, setOverlayText] = useState("");
  const [overlayPosition, setOverlayPosition] = useState("bottom");
  const [overlaySize, setOverlaySize] = useState(48);
  const [overlayColor, setOverlayColor] = useState("#ffffff");
  const [exportInfo, setExportInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => setListKey((k) => k + 1);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy("create");
    try {
      const created = await api.createCampaign({
        name: name.trim(),
        description: description.trim() || undefined,
        project_id: projectId || null,
      });
      setOpen(created);
      setCreating(false);
      setName("");
      setDescription("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat campaign");
    } finally {
      setBusy("");
    }
  };

  const openCampaign = async (id: string) => {
    try {
      setOpen(await api.campaign(id));
      setExportInfo(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuka campaign");
    }
  };

  const addAsset = async () => {
    if (!open || !pickAsset || busy) return;
    setBusy("add");
    try {
      setOpen(await api.addCampaignAsset(open.id, { asset_id: pickAsset }));
      setPickAsset("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menambah aset");
    } finally {
      setBusy("");
    }
  };

  const removeAsset = async (assetId: string) => {
    if (!open) return;
    try {
      setOpen(await api.removeCampaignAsset(open.id, assetId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus aset");
    }
  };

  const changeStatus = async (status: string) => {
    if (!open) return;
    try {
      setOpen(await api.updateCampaign(open.id, { status }));
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengubah status");
    }
  };

  const renderOverlay = async () => {
    if (!open || !overlayAsset || !overlayText.trim() || busy) return;
    setBusy("overlay");
    try {
      const result = await api.renderCampaignOverlay(open.id, {
        asset_id: overlayAsset,
        text: overlayText.trim(),
        position: overlayPosition,
        font_size: overlaySize,
        color: overlayColor,
      });
      setOpen(result.campaign);
      setOverlayText("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal render overlay");
    } finally {
      setBusy("");
    }
  };

  const doExport = async () => {
    if (!open || busy) return;
    setBusy("export");
    try {
      const info = await api.exportCampaign(open.id);
      setExportInfo(`${info.filename} • ${info.asset_count} aset • ${(info.file_size / 1024).toFixed(0)} KB`);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal export");
    } finally {
      setBusy("");
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Hapus campaign ini? Aset tidak ikut terhapus.")) return;
    try {
      await api.deleteCampaign(id);
      if (open?.id === id) setOpen(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus campaign");
    }
  };

  const campaignImages = (open?.assets ?? []).filter((a) => a.file_type === "image");
  const pickable = (allAssets.data?.items ?? []).filter(
    (a) => !(open?.assets ?? []).some((inCamp) => inCamp.id === a.id)
  );

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Campaign Studio</h1>
          <p>Bundling aset kampanye, overlay typography deterministik (PIL), dan export paket zip + manifest.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating((c) => !c)}>
          {creating ? "Tutup" : "+ Campaign baru"}
        </button>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {creating ? (
        <form className="panel create-form" onSubmit={create}>
          <label>
            Nama campaign
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="mis. Launch Kopi" />
          </label>
          <label>
            Deskripsi
            <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="opsional" />
          </label>
          <label>
            Project
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">(tanpa project)</option>
              {(projects.data?.items ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy === "create"}>
            Buat campaign
          </button>
        </form>
      ) : null}

      {open ? (
        <section className="panel">
          <div className="panel-head">
            <h2>
              {open.name} <span className="muted small">({open.id})</span>
            </h2>
            <div className="plan-item-status">
              <StatusPill tone={STATUS_TONES[open.status] ?? "neutral"}>{open.status}</StatusPill>
            </div>
          </div>
          <div className="gc-actions" style={{ marginBottom: 10 }}>
            <label className="muted small">
              Status:
              <select value={open.status} onChange={(e) => changeStatus(e.target.value)} className="inline-select">
                {["draft", "active", "completed"].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {open.assets && open.assets.length > 0 ? (
            <div className="asset-grid">
              {open.assets.map((asset) => (
                <figure key={asset.id} className="asset-card asset-card-managed">
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
                      <button className="btn btn-danger scene-btn-mini" type="button" onClick={() => removeAsset(asset.id)}>
                        ✕
                      </button>
                    </div>
                    <span className="muted small">{asset.role || "—"}</span>
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : (
            <EmptyState title="Campaign masih kosong" detail="Tambahkan aset dari daftar di bawah." />
          )}

          <div className="gc-approve">
            <label>
              Tambah aset
              <select value={pickAsset} onChange={(e) => setPickAsset(e.target.value)}>
                <option value="">— pilih aset —</option>
                {pickable.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.filename}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn btn-primary" type="button" onClick={addAsset} disabled={!pickAsset || busy !== ""}>
              + Masukkan
            </button>
          </div>

          <div className="gc-approve">
            <label>
              Aset (gambar)
              <select value={overlayAsset} onChange={(e) => setOverlayAsset(e.target.value)}>
                <option value="">— pilih gambar —</option>
                {campaignImages.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.filename}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Teks overlay
              <input value={overlayText} onChange={(e) => setOverlayText(e.target.value)} placeholder="mis. Promo Pagi Ini" />
            </label>
            <label>
              Posisi
              <select value={overlayPosition} onChange={(e) => setOverlayPosition(e.target.value)}>
                {["top", "center", "bottom"].map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Ukuran font
              <input
                type="number"
                min={12}
                max={200}
                value={overlaySize}
                onChange={(e) => setOverlaySize(Number(e.target.value))}
              />
            </label>
            <label>
              Warna
              <input type="color" value={overlayColor} onChange={(e) => setOverlayColor(e.target.value)} />
            </label>
            <button
              className="btn btn-primary"
              type="button"
              onClick={renderOverlay}
              disabled={!overlayAsset || !overlayText.trim() || busy !== ""}
            >
              {busy === "overlay" ? "Merender…" : "Render overlay"}
            </button>
          </div>

          <div className="gc-actions" style={{ marginTop: 14 }}>
            <button
              className="btn btn-primary"
              type="button"
              onClick={doExport}
              disabled={busy !== "" || (open.assets?.length ?? 0) === 0}
            >
              {busy === "export" ? "Mengekspor…" : "Export paket (zip + manifest)"}
            </button>
            {exportInfo ? (
              <>
                <span className="muted small">{exportInfo}</span>
                <a className="btn" href={`/api/campaigns/${open.id}/export/download`}>
                  Unduh zip
                </a>
              </>
            ) : null}
            <button className="btn" type="button" onClick={() => { setOpen(null); refresh(); }}>
              Tutup editor
            </button>
            <button className="btn btn-danger" type="button" onClick={() => remove(open.id)}>
              Hapus campaign
            </button>
          </div>
        </section>
      ) : null}

      {campaigns.data && campaigns.data.items.length > 0 ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Campaign tersimpan</h2>
          </div>
          <ul className="list">
            {campaigns.data.items.map((c) => (
              <li key={c.id} className="list-row">
                <div>
                  <div className="list-title">{c.name}</div>
                  <div className="muted small">
                    {c.status} • {c.asset_count} aset • {new Date(c.created_at).toLocaleString("id-ID")}
                  </div>
                </div>
                <div className="plan-row-actions">
                  <button className="btn" type="button" onClick={() => openCampaign(c.id)}>
                    Buka
                  </button>
                  <button className="btn btn-danger" type="button" onClick={() => remove(c.id)}>
                    Hapus
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <EmptyState
          title="Belum ada campaign"
          detail="Campaign menggabungkan aset menjadi paket siap ekspor (zip + manifest sha256)."
        />
      )}
      {previewId ? <AssetPreview assetId={previewId} onClose={() => setPreviewId(null)} /> : null}
    </div>
  );
}
