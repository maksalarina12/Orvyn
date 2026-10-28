import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, assetFileUrl } from "../services/api";
import { assetDownloadName, downloadZip, triggerDownload } from "../lib/download";
import type { Asset, GenerationJob } from "../types/api";

function fmtSize(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return "—";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AssetPreview({
  assetId,
  ids,
  job,
  onClose,
}: {
  assetId: string;
  ids?: string[];
  job?: GenerationJob | null;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const allIds = useMemo(() => (ids && ids.length > 0 ? ids : [assetId]), [ids, assetId]);
  const [current, setCurrent] = useState(assetId);
  const [asset, setAsset] = useState<Asset | null>(null);
  const [copied, setCopied] = useState(false);
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [projectId, setProjectId] = useState("");
  const [moving, setMoving] = useState(false);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [zipping, setZipping] = useState(false);
  const [zipError, setZipError] = useState<string | null>(null);

  useEffect(() => setCurrent(assetId), [assetId]);

  useEffect(() => {
    let alive = true;
    setAsset(null);
    setMoveError(null);
    api
      .asset(current)
      .then((a) => alive && setAsset(a))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [current]);

  useEffect(() => {
    let alive = true;
    api
      .projects({})
      .then((d) => alive && setProjects(d.items.map((p) => ({ id: p.id, name: p.name }))))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    setProjectId(asset?.project_id ?? "");
    setMoveError(null);
  }, [asset]);

  const index = Math.max(0, allIds.indexOf(current));
  const isVideo = (asset?.file_type ?? (job?.mode === "text_to_video" ? "video" : "image")) === "video";
  const prompt = job?.prompt ?? asset?.prompt ?? "";
  const title = asset?.filename ?? `hasil-${current.slice(-8)}`;
  const hasMultiple = allIds.length > 1;

  const go = useCallback(
    (delta: number) => {
      if (!hasMultiple) return;
      const next = (index + delta + allIds.length) % allIds.length;
      setCurrent(allIds[next]);
    },
    [allIds, hasMultiple, index],
  );

  const downloadOne = useCallback(() => {
    triggerDownload(assetFileUrl(current), assetDownloadName(asset, current, job));
  }, [asset, current, job]);

  const downloadAll = async () => {
    setZipping(true);
    setZipError(null);
    try {
      await downloadZip(allIds);
    } catch (err) {
      setZipError(err instanceof Error ? err.message : "Unduh zip gagal");
    } finally {
      setZipping(false);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName ?? "";
      if (["INPUT", "TEXTAREA", "SELECT", "VIDEO"].includes(tag)) return;
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        go(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        go(1);
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "d") {
        e.preventDefault();
        downloadOne();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [downloadOne, go, onClose]);

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  const moveToProject = async () => {
    if (!asset || !projectId || projectId === asset.project_id) return;
    setMoving(true);
    setMoveError(null);
    try {
      const updated = await api.updateAsset(asset.id, { project_id: projectId });
      setAsset(updated);
      setProjectId(updated.project_id ?? "");
    } catch (err) {
      setMoveError(err instanceof Error ? err.message : "Gagal memindahkan aset");
    } finally {
      setMoving(false);
    }
  };

  const makeVariation = () => {
    const params = new URLSearchParams();
    if (prompt) params.set("prompt", prompt);
    const seed = job?.params?.seed;
    if (seed !== undefined && seed !== null && seed !== "") params.set("seed", String(seed));
    if (job?.provider_id) params.set("provider", job.provider_id);
    params.set("mode", job?.mode ?? (asset?.file_type === "video" ? "text_to_video" : "text_to_image"));
    onClose();
    navigate(`/quick-generate?${params.toString()}`);
  };

  const openRemix = () => {
    onClose();
    navigate(`/remix-improve?source=${encodeURIComponent(current)}`);
  };

  return (
    <div className="preview-backdrop" onMouseDown={onClose}>
      <div
        className="preview"
        role="dialog"
        aria-modal="true"
        aria-label={`Pratinjau ${title}`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="preview-head">
          <div className="preview-title">
            <span className="preview-kicker">Pratinjau aset</span>
            <h2 title={title}>{title}</h2>
          </div>
          <div className="preview-nav">
            {hasMultiple ? (
              <>
                <button type="button" onClick={() => go(-1)} aria-label="Hasil sebelumnya" title="← sebelumnya">
                  ‹
                </button>
                <span>
                  {index + 1}/{allIds.length}
                </span>
                <button type="button" onClick={() => go(1)} aria-label="Hasil berikutnya" title="→ berikutnya">
                  ›
                </button>
              </>
            ) : null}
            <button className="preview-close" onClick={onClose} aria-label="Tutup pratinjau">
              Esc
            </button>
          </div>
        </div>

        <div className="preview-stage">
          {isVideo ? (
            <video key={current} src={assetFileUrl(current)} controls autoPlay loop playsInline />
          ) : (
            <img src={assetFileUrl(current)} alt={title} />
          )}
          {hasMultiple ? (
            <>
              <button type="button" className="preview-arrow is-prev" onClick={() => go(-1)} aria-label="Sebelumnya">
                ‹
              </button>
              <button type="button" className="preview-arrow is-next" onClick={() => go(1)} aria-label="Berikutnya">
                ›
              </button>
            </>
          ) : null}
        </div>

        <div className="preview-meta">
          <div className="meta-grid">
            <div className="meta-item">
              <span>Dimensi</span>
              <b>{asset?.width && asset?.height ? `${asset.width}×${asset.height}` : "—"}</b>
            </div>
            <div className="meta-item">
              <span>Ukuran</span>
              <b>{fmtSize(asset?.file_size)}</b>
            </div>
            <div className="meta-item">
              <span>Tipe</span>
              <b>{asset?.mime_type ?? (isVideo ? "video" : "image")}</b>
            </div>
            <div className="meta-item">
              <span>Provider</span>
              <b>{job?.provider_id ?? asset?.source ?? "—"}</b>
            </div>
          </div>

          {prompt ? (
            <div className="preview-prompt">
              <div className="preview-prompt-head">
                <span>Prompt</span>
                <button type="button" className="btn btn-small" onClick={copyPrompt}>
                  {copied ? "Tersalin" : "Salin"}
                </button>
              </div>
              <p>{prompt}</p>
            </div>
          ) : null}

          {projects.length > 0 && asset ? (
            <div className="preview-project">
              <span className="preview-project-label">Proyek</span>
              <select value={projectId} onChange={(e) => setProjectId(e.target.value)} aria-label="Pilih proyek">
                <option value="">— belum ada —</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-small"
                onClick={moveToProject}
                disabled={moving || !projectId || projectId === asset.project_id}
              >
                {moving ? "Memindahkan…" : asset.project_id === projectId && projectId ? "Sudah di proyek" : "Pindahkan"}
              </button>
              {moveError ? <span className="preview-error">{moveError}</span> : null}
            </div>
          ) : null}
          {zipError ? <div className="preview-error">{zipError}</div> : null}
        </div>

        <div className="preview-actions">
          <button className="btn btn-primary" type="button" onClick={downloadOne} title="Unduh (⌘D)">
            Unduh
          </button>
          {hasMultiple ? (
            <button className="btn" type="button" onClick={downloadAll} disabled={zipping}>
              {zipping ? "Menyiapkan…" : `Zip semua (${allIds.length})`}
            </button>
          ) : null}
          <button className="btn" type="button" onClick={makeVariation} disabled={!prompt}>
            Variasi
          </button>
          <button className="btn" type="button" onClick={openRemix}>
            Remix
          </button>
          <span className="preview-keys">← → ganti · ⌘D unduh · Esc tutup</span>
          <code className="preview-id">{current}</code>
          <button className="btn" type="button" onClick={onClose}>
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}
