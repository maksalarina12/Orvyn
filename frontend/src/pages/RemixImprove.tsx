import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { EmptyState, StatusPill } from "../components/ui";
import { AssetPreview } from "../components/AssetPreview";
import type { Asset, GenerationJob, ProviderStatus } from "../types/api";

export function RemixImprove() {
  const assets = useApiState<{ items: Asset[] }>(() => api.assets({ limit: 100 }), []);
  const providers = useApiState<{ items: ProviderStatus[] }>(() => api.providers(), []);
  const projects = useApiState<{ items: { id: string; name: string }[] }>(() => api.projects(), []);

  const [sourceId, setSourceId] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [providerId, setProviderId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [seed, setSeed] = useState("");
  const [steps, setSteps] = useState(28);
  const [guidance, setGuidance] = useState(2.5);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const i2iProviders = (providers.data?.items ?? []).filter(
    (p) => p.enabled && p.health.ok && p.capabilities.modes.includes("image_to_image")
  );

  useEffect(() => {
    if (!providers.data || providerId || !i2iProviders.length) return;
    setProviderId(i2iProviders[0].provider_id);
  }, [providers.data, providerId, i2iProviders.length]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed" || job.status === "cancelled") return;
    const source = new EventSource(`/api/generations/${job.id}/events`);
    const onMessage = (event: MessageEvent) => {
      try {
        const fresh = JSON.parse(event.data) as GenerationJob;
        setJob(fresh);
        if (fresh.status === "completed" || fresh.status === "failed" || fresh.status === "cancelled") {
          source.close();
          window.dispatchEvent(new Event("orvyn:jobs-changed"));
        }
      } catch {
        /* ignore malformed event */
      }
    };
    source.addEventListener("job", onMessage as EventListener);
    return () => source.close();
  }, [job?.id, job?.status]);

  useEffect(() => {
    const incoming = searchParams.get("source");
    if (!incoming) return;
    setSourceId(incoming);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("source");
        return next;
      },
      { replace: true },
    );
  }, [searchParams, setSearchParams]);

  const images = (assets.data?.items ?? []).filter((a) => a.file_type === "image");
  const source = images.find((a) => a.id === sourceId) ?? null;

  const submit = async () => {
    if (!source || !prompt.trim() || !providerId || busy) return;
    setError(null);
    setBusy(true);
    try {
      const created = await api.submitGeneration({
        provider_id: providerId,
        mode: "image_to_image",
        prompt: prompt.trim(),
        params: {
          ...(providerId === "hf_space_kontext" ? { steps, guidance_scale: guidance } : {}),
          ...(seed ? { seed: Number(seed) } : {}),
          num_images: 1,
        },
        project_id: projectId || null,
        source_asset_id: source.id,
      });
      setJob(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengirim job");
    } finally {
      setBusy(false);
    }
  };

  if (assets.loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Remix & Improve</h1>
          <p>Revisi gambar yang ada: ubah mood, background, atau gaya. Aset sumber tidak pernah berubah — hasilnya versi baru.</p>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}
      {i2iProviders.length === 0 ? (
        <div className="error-banner">
          Belum ada provider image-to-image yang aktif. Buka <strong>Model & Backend</strong> dan aktifkan
          “HF Space Kontext (image-to-image)” dengan konfirmasi eksplisit.
        </div>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h2>1. Pilih gambar sumber</h2>
          <span className="muted small">{images.length} gambar</span>
        </div>
        {images.length === 0 ? (
          <EmptyState title="Belum ada gambar" detail="Generate atau unggah gambar dulu di modul lain." />
        ) : (
          <div className="asset-grid">
            {images.map((a) => (
              <button
                key={a.id}
                type="button"
                className={`asset-card${sourceId === a.id ? " asset-card-selected" : ""}`}
                onClick={() => setSourceId(a.id)}
              >
                <img src={assetFileUrl(a.id)} alt={a.filename} loading="lazy" />
                <span className="asset-name">{a.filename}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>2. Instruksi revisi</h2>
        </div>
        {source ? (
          <div className="ri-source-preview">
            <img src={assetFileUrl(source.id)} alt={source.filename} />
            <div className="muted small">
              {source.filename} — {source.width}×{source.height} {source.prompt ? `• prompt asal: “${source.prompt.slice(0, 80)}…”` : ""}
            </div>
          </div>
        ) : (
          <div className="muted small">Pilih gambar sumber dulu di atas.</div>
        )}

        <div className="ri-form">
          <label className="ri-prompt">
            Instruksi
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="mis. Ubah suasana menjadi malam hari dengan lampu hangat, pertahankan komposisi"
            />
          </label>
          <label>
            Provider
            <select value={providerId} onChange={(e) => setProviderId(e.target.value)}>
              {i2iProviders.map((p) => (
                <option key={p.provider_id} value={p.provider_id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Seed (opsional)
            <input type="number" value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="acak" />
          </label>
          {providerId === "hf_space_kontext" ? (
            <>
              <label>
                Steps
                <input type="number" min={1} max={28} value={steps} onChange={(e) => setSteps(Number(e.target.value))} />
              </label>
              <label>
                Guidance
                <input
                  type="number"
                  min={1}
                  max={10}
                  step={0.5}
                  value={guidance}
                  onChange={(e) => setGuidance(Number(e.target.value))}
                />
              </label>
            </>
          ) : null}
          <label>
            Project
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">— tanpa project —</option>
              {(projects.data?.items ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="btn btn-primary"
            type="button"
            disabled={!source || !prompt.trim() || !providerId || busy || job?.status === "running" || job?.status === "queued"}
            onClick={submit}
          >
            {job && (job.status === "queued" || job.status === "running") ? "Memproses…" : "Kirim revisi"}
          </button>
        </div>
      </section>

      {job ? (
        <section className="panel">
          <div className="panel-head">
            <h2>3. Hasil</h2>
            <StatusPill
              tone={job.status === "completed" ? "ok" : job.status === "failed" ? "fail" : job.status === "cancelled" ? "warn" : "neutral"}
            >
              {job.status}
            </StatusPill>
          </div>
          {job.error ? <div className="error-banner">{job.error}</div> : null}
          {job.result_asset_ids.length > 0 ? (
            <div className="asset-grid">
              {job.result_asset_ids.map((id) => (
                <button
                  key={id}
                  type="button"
                  className="asset-card asset-card-btn"
                  onClick={() => setPreviewId(id)}
                  title="Buka pratinjau"
                >
                  <img src={assetFileUrl(id)} alt="hasil revisi" />
                  <span className="asset-name">{id}</span>
                  <span className="asset-open-hint">Pratinjau</span>
                </button>
              ))}
            </div>
          ) : job.status === "failed" ? (
            <div className="muted small">
              Revisi gagal — pesan error asli provider ditampilkan apa adanya di atas. Kuota ZeroGPU anonim sering
              menjadi penyebab; coba lagi nanti atau isi token HF di Model & Backend.
            </div>
          ) : (
            <div className="muted small">Job {job.id} diproses…</div>
          )}
        </section>
      ) : null}
      {previewId ? <AssetPreview assetId={previewId} onClose={() => setPreviewId(null)} /> : null}
    </div>
  );
}
