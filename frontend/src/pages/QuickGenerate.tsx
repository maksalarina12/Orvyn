import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { EmptyState, StatusPill } from "../components/ui";
import { PromptStudio } from "../components/PromptStudio";
import { AssetPreview } from "../components/AssetPreview";
import type { GenerationJob, ProviderStatus } from "../types/api";
import { clearPromptHistory, loadPromptHistory, pushPromptHistory } from "../lib/promptHistory";
import { loadAutoPreview, saveAutoPreview } from "../lib/prefs";

const ASPECTS: { label: string; w: number; h: number }[] = [
  { label: "1:1", w: 512, h: 512 },
  { label: "4:3", w: 576, h: 448 },
  { label: "3:2", w: 608, h: 400 },
  { label: "16:9", w: 640, h: 352 },
  { label: "9:16", w: 352, h: 640 },
];

const INITIAL_PARAMS = {
  width: 512,
  height: 512,
  steps: 4,
  guidance: 7,
  num_images: 1,
  seed: "" as string | number,
  num_frames: 16,
};

export function QuickGenerate() {
  const [tab, setTab] = useState<"langsung" | "studio">("langsung");
  const providers = useApiState<{ items: ProviderStatus[] }>(() => api.providers(), []);
  const [providerId, setProviderId] = useState<string>("");
  const [mode, setMode] = useState<string>("text_to_image");
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [params, setParams] = useState({ ...INITIAL_PARAMS });
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>(() => loadPromptHistory());
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [autoPreview, setAutoPreview] = useState(() => loadAutoPreview());
  const [allowFallback, setAllowFallback] = useState(true);
  const autoPreviewed = useRef<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    if (!providers.data) return;
    const usable = providers.data.items.find((p) => p.enabled && p.health.ok);
    if (usable && !providerId) setProviderId(usable.provider_id);
  }, [providers.data]);

  useEffect(() => {
    if (providers.loading) return;
    const current = (providers.data?.items ?? []).find((p) => p.provider_id === providerId);
    if (!current) return;
    const modes = current.capabilities.modes;
    setMode((prev) => {
      if (modes.includes(prev)) return prev;
      if (modes.includes("text_to_image")) return "text_to_image";
      return modes[0] ?? "text_to_image";
    });
  }, [providerId, providers.data]);

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) return;
    const source = new EventSource(`/api/generations/${job.id}/events`);
    const onMessage = (event: MessageEvent) => {
      try {
        const fresh = JSON.parse(event.data) as GenerationJob;
        setJob((prev) => (prev && prev.id === fresh.id ? fresh : prev));
        if (fresh.status === "failed") setError(fresh.error ?? "Generation gagal");
        else if (fresh.status !== "queued" && fresh.status !== "running") setError(null);
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
    const deepLink = searchParams.get("preview");
    if (deepLink) setPreviewId(deepLink);
  }, [searchParams]);

  useEffect(() => {
    if (!job) return;
    if (job.status === "completed" && job.result_asset_ids.length > 0 && autoPreviewed.current !== job.id) {
      autoPreviewed.current = job.id;
      if (autoPreview) setPreviewId(job.result_asset_ids[0]);
    }
  }, [job, autoPreview]);

  useEffect(() => {
    const promptParam = searchParams.get("prompt");
    if (!promptParam) return;
    setPrompt(promptParam);
    const seed = searchParams.get("seed");
    if (seed) setParams((prev) => ({ ...prev, seed }));
    const provider = searchParams.get("provider");
    if (provider) setProviderId(provider);
    const modeParam = searchParams.get("mode");
    if (modeParam) setMode(modeParam);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        ["prompt", "seed", "provider", "mode"].forEach((key) => next.delete(key));
        return next;
      },
      { replace: true },
    );
  }, [searchParams, setSearchParams]);

  if (providers.loading) return <div className="page-loading">Loading…</div>;

  const items = providers.data?.items ?? [];
  const usable = items.filter((p) => p.enabled && p.health.ok);
  const enabledNotOk = items.filter((p) => p.enabled && !p.health.ok);
  const disabled = items.filter((p) => !p.enabled);
  const selected = items.find((p) => p.provider_id === providerId) ?? null;
  const selectedModes = selected?.capabilities.modes ?? [];
  const isVideoMode = mode === "text_to_video";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!providerId || !prompt.trim() || submitting) return;
    if (!selectedModes.includes(mode)) {
      setError(`Mode "${mode}" tidak didukung provider ini. Pilih mode yang tersedia.`);
      return;
    }
    if (selected?.is_external) {
      const proceed = window.confirm(
        `Prompt akan dikirim ke "${selected.display_name}" ${
          selected.health?.space_url ? `(${selected.health.space_url})` : ""
        } — layanan pihak ketiga, bukan lokal. Lanjutkan?`
      );
      if (!proceed) return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.submitGeneration({
        provider_id: providerId,
        mode,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim() || null,
        allow_fallback: allowFallback,
        params: isVideoMode
          ? {
              num_frames: params.num_frames,
              steps: params.steps,
              num_images: params.num_images,
              ...(params.seed !== "" && params.seed !== undefined ? { seed: Number(params.seed) } : {}),
            }
          : {
              width: params.width,
              height: params.height,
              steps: params.steps,
              guidance: params.guidance,
              num_images: params.num_images,
              ...(params.seed !== "" && params.seed !== undefined ? { seed: Number(params.seed) } : {}),
            },
      });
      setJob(created);
      window.dispatchEvent(new Event("orvyn:jobs-changed"));
      setHistory(pushPromptHistory(prompt));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat job");
    } finally {
      setSubmitting(false);
    }
  };

  const cancel = async () => {
    if (!job) return;
    try {
      setJob(await api.cancelJob(job.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal cancel");
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Quick Generate</h1>
          <p>Generasi gambar langsung. Tujuan tersimpan otomatis ke Project Assets.</p>
        </div>
        <div className="qg-tabs">
          <button
            className={`btn ${tab === "langsung" ? "btn-primary" : ""}`}
            type="button"
            onClick={() => setTab("langsung")}
          >
            Langsung
          </button>
          <button
            className={`btn ${tab === "studio" ? "btn-primary" : ""}`}
            type="button"
            onClick={() => setTab("studio")}
          >
            Studio Prompt
          </button>
        </div>
        {selected && tab === "langsung" ? (
          <StatusPill tone={selected.health.ok ? "ok" : "warn"}>
            provider: {selected.display_name}
          </StatusPill>
        ) : null}
      </header>

      {tab === "studio" ? <PromptStudio /> : null}

      {tab === "langsung" ? (
        <>
      {usable.length === 0 ? (
        <EmptyState
          title="Belum ada provider yang aktif"
          detail={
            items.length > 0
              ? "Minim satu provider harus diaktifkan di Model & Backend Settings (dengan konfirmasi). Fallback lokal memerlukan unduhan model."
              : "Gateway generation masih menyiapkan registry provider."
          }
          hint="Buka Model & Backend Settings untuk aktivasi provider."
        />
      ) : null}

      {enabledNotOk.map((p) => (
        <div key={p.provider_id} className="error-banner">
          Provider {p.display_name} aktif tapi tidak siap seat ini: {p.health.reason ?? "unknown"}{" "}
          <Link to="/models">Perbaiki di Model &amp; Backend →</Link>
        </div>
      ))}

      {enabledNotOk.length > 0 && disabled.length > 0 && usable.length === 0 ? (
        <div className="muted small">
          Ada {disabled.length} provider dinonaktifkan: {disabled.map((d) => d.display_name).join(", ")}.
        </div>
      ) : null}

      {error ? <div className="error-banner">{error}</div> : null}

      <form className="panel qg-form" onSubmit={submit}>
        <label className="qg-prompt">
          <span className="label-row">
            Prompt
            <span className="label-hint">⌘⏎ kirim</span>
          </span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                e.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder={isVideoMode ? "Deskripsikan klip video yang kamu inginkan…" : "Deskripsikan gambar yang kamu inginkan…"}
            rows={3}
            required
          />
        </label>
        {history.length > 0 ? (
          <div className="history-row">
            <span className="history-label">Riwayat</span>
            {history.map((h, i) => (
              <button
                key={`${i}-${h.slice(0, 12)}`}
                type="button"
                className="chip"
                title={h}
                onClick={() => setPrompt(h)}
              >
                {h.length > 44 ? `${h.slice(0, 44)}…` : h}
              </button>
            ))}
            <button
              type="button"
              className="chip chip-clear"
              onClick={() => setHistory(clearPromptHistory())}
              title="Hapus riwayat prompt dari perangkat ini"
            >
              hapus
            </button>
          </div>
        ) : null}
        <div className="qg-row">
          <label>
            Provider
            <select value={providerId} onChange={(e) => setProviderId(e.target.value)}>
              {usable.map((p) => (
                <option key={p.provider_id} value={p.provider_id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Mode
            <select
              value={mode}
              onChange={(e) => {
                setMode(e.target.value);
                setJob(null);
              }}
            >
              {selectedModes.includes("text_to_image") ? <option value="text_to_image">Gambar</option> : null}
              {selectedModes.includes("text_to_video") ? <option value="text_to_video">Video (t2v)</option> : null}
            </select>
          </label>
          {!isVideoMode ? (
            <>
              <label>
                Aspect
                <select
                  value={`${params.width}x${params.height}`}
                  onChange={(e) => {
                    const found = ASPECTS.find((a) => `${a.w}x${a.h}` === e.target.value);
                    if (found) setParams((p) => ({ ...p, width: found.w, height: found.h }));
                  }}
                >
                  {ASPECTS.map((a) => (
                    <option key={a.label} value={`${a.w}x${a.h}`}>
                      {a.label} ({a.w}×{a.h})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Jumlah gambar
                <select
                  value={params.num_images}
                  onChange={(e) => setParams((p) => ({ ...p, num_images: Number(e.target.value) }))}
                >
                  {[1, 2, 3, 4].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <>
              <label>
                Jumlah frame
                <select
                  value={params.num_frames}
                  onChange={(e) => setParams((p) => ({ ...p, num_frames: Number(e.target.value) }))}
                >
                  {[16, 24, 32, 48, 64].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Jumlah video
                <select
                  value={params.num_images}
                  onChange={(e) => setParams((p) => ({ ...p, num_images: Number(e.target.value) }))}
                >
                  {[1, 2].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
        </div>

        <details className="qg-advanced">
          <summary>Pengaturan lanjut</summary>
          <div className="qg-row">
            <label>
              Steps {isVideoMode ? "(1–50)" : "(1–50)"}
              <input
                type="number"
                min={1}
                max={50}
                value={params.steps}
                onChange={(e) => setParams((p) => ({ ...p, steps: Number(e.target.value) }))}
              />
            </label>
            {!isVideoMode ? (
              <label>
                Guidance (0–30)
                <input
                  type="number"
                  min={0}
                  max={30}
                  step="0.5"
                  value={params.guidance}
                  onChange={(e) => setParams((p) => ({ ...p, guidance: Number(e.target.value) }))}
                />
              </label>
            ) : null}
            <label>
              Seed (kosong = otomatis)
              <input
                type="number"
                value={params.seed}
                onChange={(e) => setParams((p) => ({ ...p, seed: e.target.value === "" ? "" : Number(e.target.value) }))}
              />
            </label>
          </div>
          {!isVideoMode ? (
            <label className="qg-prompt">
              Negative prompt (opsional)
              <textarea value={negativePrompt} onChange={(e) => setNegativePrompt(e.target.value)} rows={2} />
            </label>
          ) : null}
        </details>

        <div className="qg-actions">
          <button className="btn btn-primary" type="submit" disabled={submitting || usable.length === 0}>
            {submitting ? "Mengirim job…" : "Generate"}
          </button>
          {job && (job.status === "queued" || job.status === "running") ? (
            <button className="btn" type="button" onClick={cancel}>
              Cancel
            </button>
          ) : null}
          <label className="toggle-inline">
            <input
              type="checkbox"
              checked={autoPreview}
              onChange={(e) => {
                setAutoPreview(e.target.checked);
                saveAutoPreview(e.target.checked);
              }}
            />
            Pratinjau otomatis
          </label>
          <label className="toggle-inline" title="Kalau provider gagal (kuota/offline), coba provider aktif lain yang mendukung mode ini">
            <input
              type="checkbox"
              checked={allowFallback}
              onChange={(e) => setAllowFallback(e.target.checked)}
            />
            Fallback otomatis
          </label>
        </div>
      </form>

      {job ? (
        <section className="panel">
          <div className="panel-head">
            <h2>
              Job <code>{job.id}</code>
            </h2>
            <StatusPill
              tone={
                job.status === "completed" ? "ok" : job.status === "failed" ? "fail" : job.status === "cancelled" ? "warn" : "neutral"
              }
            >
              {job.status.toUpperCase()}
            </StatusPill>
          </div>
          <ul className="list">
            <li className="list-row muted small">
              mode: {job.mode} • attempts: {job.attempts}/{job.max_attempts} • provider: {job.provider_id}
              {job.provider_chain && job.provider_chain.length > 1
                ? ` • chain: ${job.provider_chain.join(" → ")}`
                : ""}
            </li>
            {job.error ? <li className="list-row error-banner">{job.error}</li> : null}
          </ul>
          {job.status === "completed" && job.result_asset_ids.length > 0 ? (
            <div className="asset-grid">
              {job.result_asset_ids.map((assetId) => (
                <figure key={assetId} className="asset-card">
                  <button
                    type="button"
                    className="asset-open"
                    onClick={() => setPreviewId(assetId)}
                    title="Buka pratinjau"
                  >
                    {job.mode === "text_to_video" ? (
                      <span className="film-video">▶ VIDEO</span>
                    ) : (
                      <img src={assetFileUrl(assetId)} alt={assetId} loading="lazy" />
                    )}
                    <span className="asset-open-hint">Pratinjau</span>
                  </button>
                  <figcaption>
                    <div className="flex-between">
                      <span className="asset-name">{assetId}</span>
                      <a className="asset-dl" href={assetFileUrl(assetId)}>
                        Unduh
                      </a>
                    </div>
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : null}
          {job.status === "queued" || job.status === "running" ? (
            <p className="muted small">Status diperbarui tiap 2 detik dari backend — bukan estimasi palsu.</p>
          ) : null}
        </section>
      ) : null}
        </>
      ) : null}

      {previewId ? (
        <AssetPreview
          assetId={previewId}
          ids={job?.result_asset_ids}
          job={job}
          onClose={() => {
            setPreviewId(null);
            if (searchParams.get("preview")) setSearchParams({}, { replace: true });
          }}
        />
      ) : null}
    </div>
  );
}
