import { useEffect, useMemo, useState } from "react";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { AssetPreview } from "./AssetPreview";
import type { GenerationJob, PromptStudioBrief, PromptStudioMeta, PromptStudioPreview, ProviderStatus } from "../types/api";

const ASPECTS = [
  { label: "1:1", w: 512, h: 512 },
  { label: "4:3", w: 576, h: 448 },
  { label: "3:2", w: 608, h: 400 },
  { label: "16:9", w: 640, h: 352 },
  { label: "9:16", w: 352, h: 640 },
];

const PLACEMENT_LABELS: Record<string, string> = {
  none: "Tanpa negative space (subjek full frame)",
  left: "Subjek kiri → ruang kosong kanan (untuk headline)",
  right: "Subjek kanan → ruang kosong kiri (untuk headline)",
  top: "Subjek bawah → ruang kosong atas",
  center: "Subjek tengah → ruang kosong simetris",
};

const STYLE_LABELS: Record<string, string> = {
  realistic: "Realistis (foto asli)",
  cinematic: "Kinematis (film still)",
  studio: "Studio kampanye (iklan premium)",
  render3d: "3D render",
  illustration: "Ilustrasi flat",
  analog: "Analog 35mm",
};

const LIGHTING_LABELS: Record<string, string> = {
  soft_daylight: "Siang lembut",
  golden_hour: "Golden hour",
  studio_softbox: "Softbox studio",
  moody_low: "Moody low-key",
  bright_airy: "Terang & airy",
  neon_night: "Neon malam",
};

const MOOD_LABELS: Record<string, string> = {
  calm: "Tenang",
  energetic: "Energik",
  premium: "Premium",
  playful: "Playful",
  mysterious: "Misterius",
  nostalgic: "Nostalgia",
};

const VARIANT_MODE_LABELS: Record<string, string> = {
  styles: "Beda style",
  angles: "Beda angle",
  both: "Dua-duanya (style + angle)",
};

function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

type CardState = {
  providerId: string;
  job: GenerationJob | null;
  error: string | null;
  copied: boolean;
};

export function PromptStudio() {
  const meta = useApiState<PromptStudioMeta>(() => api.promptStudioMeta(), []);
  const providers = useApiState<{ items: ProviderStatus[] }>(() => api.providers(), []);
  const [previewAsset, setPreviewAsset] = useState<{ id: string; ids: string[]; job: GenerationJob } | null>(null);
  const [brief, setBrief] = useState<PromptStudioBrief>({
    subject: "",
    shot: "hero",
    placement: "none",
    style: "realistic",
    lighting: "soft_daylight",
    mood: "calm",
    extra: "",
    variant_mode: "styles",
    count: 4,
  });
  const [preview, setPreview] = useState<PromptStudioPreview | null>(null);
  const [building, setBuilding] = useState(false);
  const [buildError, setBuildError] = useState<string | null>(null);
  const [aspect, setAspect] = useState("512x512");
  const [numImages, setNumImages] = useState(1);
  const [steps, setSteps] = useState(20);
  const [seed, setSeed] = useState<string | number>("");
  const [cards, setCards] = useState<Record<string, CardState>>({});

  const t2iProviders = useMemo(
    () => (providers.data?.items ?? []).filter((p) => p.enabled && p.health.ok && p.capabilities.modes.includes("text_to_image")),
    [providers.data]
  );

  useEffect(() => {
    if (!preview || t2iProviders.length === 0) return;
    setCards((prev) => {
      const next: Record<string, CardState> = {};
      for (const v of preview.variants) {
        next[v.id] = prev[v.id]?.job ? prev[v.id] : { providerId: t2iProviders[0].provider_id, job: null, error: null, copied: false };
      }
      return next;
    });
  }, [preview, t2iProviders]);

  const activeJobsKey = Object.entries(cards)
    .filter(([, c]) => c.job && (c.job.status === "queued" || c.job.status === "running"))
    .map(([variantId, c]) => `${variantId}:${c.job!.id}`)
    .join(",");

  useEffect(() => {
    if (!activeJobsKey) return;
    const sources = activeJobsKey.split(",").map((pair) => {
      const [variantId, jobId] = pair.split(":");
      const source = new EventSource(`/api/generations/${jobId}/events`);
      const onMessage = (event: MessageEvent) => {
        try {
          const fresh = JSON.parse(event.data) as GenerationJob;
          setCards((prev) => {
            const current = prev[variantId];
            if (!current || current.job?.id !== fresh.id) return prev;
            return {
              ...prev,
              [variantId]: {
                ...current,
                job: fresh,
                error: fresh.status === "failed" ? fresh.error ?? "Generation gagal" : null,
              },
            };
          });
          if (fresh.status === "completed" || fresh.status === "failed" || fresh.status === "cancelled") {
            source.close();
            window.dispatchEvent(new Event("orvyn:jobs-changed"));
          }
        } catch {
          /* ignore malformed event */
        }
      };
      source.addEventListener("job", onMessage as EventListener);
      return source;
    });
    return () => sources.forEach((source) => source.close());
  }, [activeJobsKey]);

  if (meta.loading || providers.loading) return <div className="page-loading">Loading…</div>;
  if (meta.error) return <div className="error-banner">Meta prompt studio gagal: {meta.error}</div>;

  const meta_ = meta.data!;
  const build = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brief.subject.trim() || building) return;
    setBuilding(true);
    setBuildError(null);
    try {
      setPreview(await api.promptStudioPreview({ ...brief, subject: brief.subject.trim() }));
      setCards({});
    } catch (err) {
      setBuildError(err instanceof Error ? err.message : "Gagal membangun prompt");
    } finally {
      setBuilding(false);
    }
  };

  const generateVariant = async (variantId: string, variantPrompt: string) => {
    const card = cards[variantId];
    if (!card || !card.providerId) return;
    const provider = t2iProviders.find((p) => p.provider_id === card.providerId);
    if (provider?.is_external) {
      const proceed = window.confirm(
        `Prompt varian ini akan dikirim ke "${provider.display_name}" — layanan pihak ketiga, bukan lokal. Lanjutkan?`
      );
      if (!proceed) return;
    }
    const [w, h] = aspect.split("x").map(Number);
    setCards((prev) => ({ ...prev, [variantId]: { ...prev[variantId], job: null, error: null, copied: false } }));
    try {
      const created = await api.submitGeneration({
        provider_id: card.providerId,
        mode: "text_to_image",
        prompt: variantPrompt,
        negative_prompt: null,
        params: {
          width: w,
          height: h,
          steps,
          num_images: numImages,
          ...(seed !== "" && seed !== undefined ? { seed: Number(seed) } : {}),
        },
      });
      setCards((prev) => ({ ...prev, [variantId]: { ...prev[variantId], job: created, error: null } }));
      window.dispatchEvent(new Event("orvyn:jobs-changed"));
    } catch (err) {
      setCards((prev) => ({
        ...prev,
        [variantId]: { ...prev[variantId], error: err instanceof Error ? err.message : "Gagal membuat job" },
      }));
    }
  };

  return (
    <div>
      <form className="panel qg-form" onSubmit={build}>
        <div className="ps-intro muted small">
          Isi brief terstruktur → backend menyusun <strong>mega prompt dasar</strong> (anchor subjek konsisten) + varian
          untuk konsistensi antar gambar. Setiap varian punya tombol Generate dan Salin.
        </div>
        <label className="qg-prompt">
          Subjek utama (apa yang digambar) *
          <textarea
            value={brief.subject}
            onChange={(e) => setBrief((b) => ({ ...b, subject: e.target.value }))}
            placeholder="mis. kopi susu botol kaca dengan label minimalis"
            rows={2}
            required
          />
        </label>
        <div className="qg-row">
          <label>
            Jenis shot
            <select value={brief.shot} onChange={(e) => setBrief((b) => ({ ...b, shot: e.target.value }))}>
              {meta_.shots.map((s) => (
                <option key={s} value={s}>
                  {label(meta_.shot_labels, s)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Negative space
            <select value={brief.placement} onChange={(e) => setBrief((b) => ({ ...b, placement: e.target.value }))}>
              {meta_.placements.map((p) => (
                <option key={p} value={p}>
                  {label(PLACEMENT_LABELS, p)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Style dasar
            <select value={brief.style} onChange={(e) => setBrief((b) => ({ ...b, style: e.target.value }))}>
              {meta_.styles.map((s) => (
                <option key={s} value={s}>
                  {label(STYLE_LABELS, s)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="qg-row">
          <label>
            Pencahayaan
            <select value={brief.lighting} onChange={(e) => setBrief((b) => ({ ...b, lighting: e.target.value }))}>
              {meta_.lightings.map((l) => (
                <option key={l} value={l}>
                  {label(LIGHTING_LABELS, l)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Mood
            <select value={brief.mood} onChange={(e) => setBrief((b) => ({ ...b, mood: e.target.value }))}>
              {meta_.moods.map((m) => (
                <option key={m} value={m}>
                  {label(MOOD_LABELS, m)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Varian
            <select
              value={brief.variant_mode}
              onChange={(e) => setBrief((b) => ({ ...b, variant_mode: e.target.value as PromptStudioBrief["variant_mode"] }))}
            >
              {meta_.variant_modes.map((m) => (
                <option key={m} value={m}>
                  {label(VARIANT_MODE_LABELS, m)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Jumlah varian
            <select value={brief.count} onChange={(e) => setBrief((b) => ({ ...b, count: Number(e.target.value) }))}>
              {[2, 3, 4, 5, 6].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="qg-prompt">
          Catatan tambahan (opsional — masuk ke mega prompt)
          <textarea
            value={brief.extra}
            onChange={(e) => setBrief((b) => ({ ...b, extra: e.target.value }))}
            placeholder="mis. label brand ORVYN, properti marmer, latar pastel"
            rows={2}
          />
        </label>
        <div className="qg-actions">
          <button className="btn btn-primary" type="submit" disabled={building || !brief.subject.trim()}>
            {building ? "Menyusun…" : "Bangun prompt"}
          </button>
        </div>
      </form>

      {buildError ? <div className="error-banner">{buildError}</div> : null}

      {preview ? (
        <>
          <section className="panel ps-base">
            <div className="panel-head">
              <h2>Mega prompt dasar (anchor konsisten)</h2>
              <button
                className="btn btn-small"
                type="button"
                onClick={async () => {
                  const ok = await copyText(preview.base_mega_prompt);
                  if (ok) window.alert("Mega prompt dasar disalin ke clipboard.");
                }}
              >
                Salin
              </button>
            </div>
            <p className="ps-prompt">{preview.base_mega_prompt}</p>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Pengaturan generate (berlaku semua varian)</h2>
            </div>
            <div className="qg-row">
              <label>
                Aspect
                <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
                  {ASPECTS.map((a) => (
                    <option key={a.label} value={`${a.w}x${a.h}`}>
                      {a.label} ({a.w}×{a.h})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Jumlah gambar
                <select value={numImages} onChange={(e) => setNumImages(Number(e.target.value))}>
                  {[1, 2, 3, 4].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Steps (1–50)
                <input type="number" min={1} max={50} value={steps} onChange={(e) => setSteps(Number(e.target.value))} />
              </label>
              <label>
                Seed (kosong = otomatis)
                <input
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value === "" ? "" : Number(e.target.value))}
                />
              </label>
            </div>
            {t2iProviders.length === 0 ? (
              <div className="error-banner">
                Tidak ada provider gambar yang aktif & siap. Aktifkan minimal satu di Model &amp; Backend Settings.
              </div>
            ) : null}
          </section>

          <div className="ps-grid">
            {preview.variants.map((v) => {
              const card = cards[v.id];
              const job = card?.job ?? null;
              return (
                <div key={v.id} className="panel ps-card">
                  <div className="panel-head">
                    <h3>{v.label}</h3>
                    <span className="muted small">{v.hint}</span>
                  </div>
                  <p className="ps-prompt small">{v.prompt}</p>
                  <div className="ps-actions">
                    <select
                      value={card?.providerId ?? ""}
                      onChange={(e) =>
                        setCards((prev) => ({ ...prev, [v.id]: { ...prev[v.id], providerId: e.target.value } }))
                      }
                    >
                      {t2iProviders.map((p) => (
                        <option key={p.provider_id} value={p.provider_id}>
                          {p.display_name}
                        </option>
                      ))}
                    </select>
                    <button
                      className="btn btn-primary btn-small"
                      type="button"
                      disabled={!card?.providerId || (job ? job.status === "queued" || job.status === "running" : false)}
                      onClick={() => generateVariant(v.id, v.prompt)}
                    >
                      {job && (job.status === "queued" || job.status === "running")
                        ? job.status === "running"
                          ? "Berjalan…"
                          : "Mengantre…"
                        : "Generate"}
                    </button>
                    <button
                      className="btn btn-small"
                      type="button"
                      onClick={async () => {
                        const ok = await copyText(v.prompt);
                        setCards((prev) => ({ ...prev, [v.id]: { ...prev[v.id], copied: ok } }));
                      }}
                    >
                      {card?.copied ? "Tersalin ✓" : "Salin"}
                    </button>
                  </div>
                  {card?.error ? <div className="error-banner">{card.error}</div> : null}
                  {job && job.status !== "completed" && job.error ? (
                    <div className="error-banner">{job.error}</div>
                  ) : null}
                  {job && (job.status === "queued" || job.status === "running") ? (
                    <p className="muted small">
                      {job.provider_id} • {job.status} • diperbarui tiap 2 detik
                    </p>
                  ) : null}
                  {job && job.status === "completed" && job.result_asset_ids.length > 0 ? (
                    <div className="asset-grid ps-results">
                      {job.result_asset_ids.map((assetId) => (
                        <figure key={assetId} className="asset-card">
                          <button
                            type="button"
                            className="asset-open"
                            onClick={() => setPreviewAsset({ id: assetId, ids: job.result_asset_ids, job })}
                            title="Buka pratinjau"
                          >
                            <img src={assetFileUrl(assetId)} alt={assetId} loading="lazy" />
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
                  {job && job.status === "failed" ? <p className="muted small">Coba provider lain di dropdown.</p> : null}
                </div>
              );
            })}
          </div>
        </>
      ) : null}

      {previewAsset ? (
        <AssetPreview
          assetId={previewAsset.id}
          ids={previewAsset.ids}
          job={previewAsset.job}
          onClose={() => setPreviewAsset(null)}
        />
      ) : null}
    </div>
  );
}
