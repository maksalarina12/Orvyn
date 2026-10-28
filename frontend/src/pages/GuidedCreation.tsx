import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { EmptyState, StatusPill } from "../components/ui";
import { AssetPreview } from "../components/AssetPreview";
import type { CreationPlan, PlanBrief, PlanPreviewItem, Project, ProviderStatus } from "../types/api";

const JOB_TERMINAL = ["completed", "failed", "cancelled"];

function jobTone(status?: string | null): "ok" | "warn" | "fail" | "neutral" {
  if (status === "completed") return "ok";
  if (status === "failed") return "fail";
  if (status === "queued" || status === "running") return "warn";
  if (status === "cancelled") return "warn";
  return "neutral";
}

interface BriefForm {
  product: string;
  audience: string;
  tone: string;
  setting: string;
  benefit: string;
  category: string;
  n_angles: number;
  aspect: string;
  steps: number;
  guidance: number;
  seed: string;
  negative_prompt: string;
  project_id: string;
}

const INITIAL_FORM: BriefForm = {
  product: "",
  audience: "",
  tone: "",
  setting: "",
  benefit: "",
  category: "product_advertisement",
  n_angles: 4,
  aspect: "16:9",
  steps: 4,
  guidance: 7,
  seed: "",
  negative_prompt: "",
  project_id: "",
};

function formToBrief(form: BriefForm): PlanBrief {
  return {
    product: form.product.trim(),
    audience: form.audience.trim() || null,
    tone: form.tone.trim() || null,
    setting: form.setting.trim() || null,
    benefit: form.benefit.trim() || null,
    category: form.category,
    n_angles: form.n_angles,
    aspect: form.aspect,
    steps: form.steps,
    guidance: form.guidance,
    ...(form.seed !== "" ? { seed: Number(form.seed) } : {}),
    negative_prompt: form.negative_prompt.trim() || null,
    project_id: form.project_id || null,
  };
}

export function GuidedCreation() {
  const meta = useApiState(() => api.planMeta(), []);
  const providers = useApiState<{ items: ProviderStatus[] }>(() => api.providers(), []);
  const projects = useApiState<{ items: Project[] }>(() => api.projects({}), []);
  const [plansKey, setPlansKey] = useState(0);
  const plans = useApiState<{ items: CreationPlan[] }>(() => api.plans({}), [plansKey]);

  const [form, setForm] = useState<BriefForm>({ ...INITIAL_FORM });
  const [preview, setPreview] = useState<PlanPreviewItem[] | null>(null);
  const [plan, setPlan] = useState<CreationPlan | null>(null);
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [providerId, setProviderId] = useState("");
  const [busy, setBusy] = useState<"" | "preview" | "save" | "approve" | "edit">("");
  const [error, setError] = useState<string | null>(null);

  const usableProviders = (providers.data?.items ?? []).filter((p) => p.enabled && p.health.ok);

  useEffect(() => {
    if (!providers.data) return;
    const usable = providers.data.items.find((p) => p.enabled && p.health.ok);
    if (usable && !providerId) setProviderId(usable.provider_id);
  }, [providers.data, providerId]);

  useEffect(() => {
    if (!plan || plan.status !== "approved") return;
    const active = plan.items?.some((item) => !JOB_TERMINAL.includes(item.job_status ?? ""));
    if (!active) return;
    const timer = setInterval(() => {
      api
        .plan(plan.id)
        .then(setPlan)
        .catch((err) => setError(err instanceof Error ? err.message : "gagal memuat status plan"));
    }, 2500);
    return () => clearInterval(timer);
  }, [plan]);

  const set = <K extends keyof BriefForm>(key: K, value: BriefForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const doPreview = async () => {
    if (!form.product.trim() || busy) return;
    setBusy("preview");
    setError(null);
    try {
      const result = await api.previewPlan(formToBrief(form));
      setPreview(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat pratinjau");
    } finally {
      setBusy("");
    }
  };

  const savePlan = async () => {
    if (!form.product.trim() || busy) return;
    setBusy("save");
    setError(null);
    try {
      const created = await api.createPlan(formToBrief(form));
      setPlan(created);
      setPreview(null);
      setPlansKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan plan");
    } finally {
      setBusy("");
    }
  };

  const approve = async () => {
    if (!plan || !providerId || busy) return;
    const selected = usableProviders.find((p) => p.provider_id === providerId);
    if (selected?.is_external) {
      const proceed = window.confirm(
        `${plan.items?.length ?? 0} prompt akan dikirim ke "${selected.display_name}" — layanan pihak ketiga, bukan lokal. Lanjutkan?`
      );
      if (!proceed) return;
    }
    setBusy("approve");
    setError(null);
    try {
      setPlan(await api.approvePlan(plan.id, providerId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyetujui plan");
    } finally {
      setBusy("");
    }
  };

  const saveItem = async (itemId: string) => {
    if (!plan || busy) return;
    setBusy("edit");
    setError(null);
    try {
      setPlan(await api.updatePlanItem(plan.id, itemId, { prompt: editDraft }));
      setEditingItem(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan prompt");
    } finally {
      setBusy("");
    }
  };

  const deletePlan = async (id: string) => {
    if (!window.confirm("Hapus plan draft ini?")) return;
    try {
      await api.deletePlan(id);
      if (plan?.id === id) setPlan(null);
      setPlansKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus plan");
    }
  };

  const reset = () => {
    setPlan(null);
    setPreview(null);
    setForm({ ...INITIAL_FORM });
  };

  if (meta.loading) return <div className="page-loading">Loading…</div>;

  const categories = meta.data?.categories ?? ["general"];
  const aspects = meta.data?.aspects ?? [{ label: "16:9", width: 640, height: 352 }];
  const categoryLabel = (value: string) => value.replace(/_/g, " ");

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Guided Creation</h1>
          <p>
            Brief terstruktur → konsep kreatif (Creative Angle Engine, deterministik) → prompt siap pakai →
            approval → antrian generation. Tanpa LLM.
          </p>
        </div>
        {plan ? <StatusPill tone={plan.status === "approved" ? "ok" : "neutral"}>plan: {plan.status}</StatusPill> : null}
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {!plan ? (
        <>
          <form
            className="panel gc-form"
            onSubmit={(e) => {
              e.preventDefault();
              void doPreview();
            }}
          >
            <label className="gc-span2">
              Produk / subjek utama *
              <input
                value={form.product}
                onChange={(e) => set("product", e.target.value)}
                placeholder="mis. meja belajar kayu jati"
                required
              />
            </label>
            <label>
              Kategori
              <select value={form.category} onChange={(e) => set("category", e.target.value)}>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {categoryLabel(c)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Project tujuan
              <select value={form.project_id} onChange={(e) => set("project_id", e.target.value)}>
                <option value="">(tanpa project)</option>
                {(projects.data?.items ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Audiens
              <input value={form.audience} onChange={(e) => set("audience", e.target.value)} placeholder="mis. pekerja remote" />
            </label>
            <label>
              Tone / mood
              <input value={form.tone} onChange={(e) => set("tone", e.target.value)} placeholder="mis. tenang dan produktif" />
            </label>
            <label>
              Setting / lokasi
              <input value={form.setting} onChange={(e) => set("setting", e.target.value)} placeholder="mis. kamar kerja minimalis" />
            </label>
            <label>
              Keunggulan yang ditonjolkan
              <input value={form.benefit} onChange={(e) => set("benefit", e.target.value)} placeholder="mis. fokus tanpa gangguan" />
            </label>
            <label>
              Jumlah angle ({form.n_angles} job = {form.n_angles} output)
              <select value={form.n_angles} onChange={(e) => set("n_angles", Number(e.target.value))}>
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Aspect
              <select value={form.aspect} onChange={(e) => set("aspect", e.target.value)}>
                {aspects.map((a) => (
                  <option key={a.label} value={a.label}>
                    {a.label} ({a.width}×{a.height})
                  </option>
                ))}
              </select>
            </label>
            <details className="gc-advanced gc-span2">
              <summary>Pengaturan lanjut</summary>
              <div className="gc-advanced-row">
                <label>
                  Steps (1–28)
                  <input
                    type="number"
                    min={1}
                    max={28}
                    value={form.steps}
                    onChange={(e) => set("steps", Number(e.target.value))}
                  />
                </label>
                <label>
                  Guidance (0–30)
                  <input
                    type="number"
                    min={0}
                    max={30}
                    step="0.5"
                    value={form.guidance}
                    onChange={(e) => set("guidance", Number(e.target.value))}
                  />
                </label>
                <label>
                  Seed (kosong = acak)
                  <input
                    type="number"
                    value={form.seed}
                    onChange={(e) => set("seed", e.target.value)}
                  />
                </label>
                <label>
                  Negative prompt (opsional)
                  <input
                    value={form.negative_prompt}
                    onChange={(e) => set("negative_prompt", e.target.value)}
                    placeholder="default aman dipakai bila kosong"
                  />
                </label>
              </div>
            </details>
            <div className="gc-actions gc-span2">
              <button className="btn btn-primary" type="submit" disabled={busy !== "" || !form.product.trim()}>
                {busy === "preview" ? "Menyusun…" : "Pratinjau rencana"}
              </button>
              <button className="btn" type="button" onClick={savePlan} disabled={busy !== "" || !form.product.trim()}>
                {busy === "save" ? "Menyimpan…" : "Simpan draft plan"}
              </button>
            </div>
          </form>

          {preview ? (
            <section className="panel">
              <div className="panel-head">
                <h2>Pratinjau rencana — {preview.length} item</h2>
              </div>
              <p className="muted small">
                Setiap item = satu job = satu output (num_images=1). Variasi prompt di sini adalah variasi konsep,
                bukan variasi generation. Preview belum disimpan — simpan dulu untuk mengedit prompt &amp; approve.
              </p>
              <ul className="list">
                {preview.map((item, index) => (
                  <li key={item.angle_id} className="list-row plan-preview-row">
                    <div>
                      <div className="list-title">
                        {index + 1}. {item.angle_label}
                      </div>
                      <code className="plan-prompt">{item.prompt}</code>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="gc-actions">
                <button className="btn btn-primary" type="button" onClick={savePlan} disabled={busy !== ""}>
                  Simpan sebagai draft &amp; edit prompt
                </button>
              </div>
            </section>
          ) : null}

          {plans.data && plans.data.items.length > 0 && !plan ? (
            <section className="panel">
              <div className="panel-head">
                <h2>Rencana tersimpan</h2>
              </div>
              <ul className="list">
                {plans.data.items.map((p) => (
                  <li key={p.id} className="list-row">
                    <div>
                      <div className="list-title">{p.title || p.id}</div>
                      <div className="muted small">
                        {categoryLabel(p.category)} • {p.status} • {p.item_count} item •{" "}
                        {new Date(p.created_at).toLocaleString("id-ID")}
                      </div>
                    </div>
                    <div className="plan-row-actions">
                      <button
                        className="btn"
                        type="button"
                        onClick={async () => {
                          try {
                            setPlan(await api.plan(p.id));
                          } catch (err) {
                            setError(err instanceof Error ? err.message : "Gagal membuka plan");
                          }
                        }}
                      >
                        Buka
                      </button>
                      {p.status === "draft" ? (
                        <button className="btn btn-danger" type="button" onClick={() => deletePlan(p.id)}>
                          Hapus
                        </button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      ) : (
        <section className="panel">
          <div className="panel-head">
            <h2>
              {plan.title} <span className="muted small">({plan.id})</span>
            </h2>
            <StatusPill tone={plan.status === "approved" ? "ok" : "neutral"}>{plan.status}</StatusPill>
          </div>
          <p className="muted small">
            {plan.brief.product} • {categoryLabel(plan.brief.category)} • {plan.brief.aspect} • steps{" "}
            {plan.brief.steps}
          </p>
          {plan.items && plan.items.length > 0 ? (
            <div className="plan-items">
              {plan.items.map((item, index) => (
                <div key={item.id} className="plan-item">
                  <div className="flex-between">
                    <div className="list-title">
                      {index + 1}. {item.angle_label}
                    </div>
                    <div className="plan-item-status">
                      {item.job_id ? (
                        <StatusPill tone={jobTone(item.job_status)}>{item.job_status ?? item.status}</StatusPill>
                      ) : (
                        <StatusPill tone="neutral">{item.status}</StatusPill>
                      )}
                    </div>
                  </div>
                  {editingItem === item.id ? (
                    <div className="plan-item-edit">
                      <textarea value={editDraft} onChange={(e) => setEditDraft(e.target.value)} rows={3} />
                      <div className="gc-actions">
                        <button className="btn btn-primary" type="button" onClick={() => saveItem(item.id)} disabled={busy !== ""}>
                          Simpan prompt
                        </button>
                        <button className="btn" type="button" onClick={() => setEditingItem(null)}>
                          Batal
                        </button>
                      </div>
                    </div>
                  ) : (
                    <code className="plan-prompt">{item.prompt}</code>
                  )}
                  {item.job_error ? <div className="error-banner">{item.job_error}</div> : null}
                  {item.job_status === "completed" && item.job_id ? (
                    <PlanItemResult jobId={item.job_id} />
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="Plan tanpa item" detail="Ada kejanggalan — plan seharusnya punya minimal satu item." />
          )}

          {plan.status === "draft" ? (
            <div className="gc-approve">
              <label>
                Provider
                <select value={providerId} onChange={(e) => setProviderId(e.target.value)}>
                  {usableProviders.map((p) => (
                    <option key={p.provider_id} value={p.provider_id}>
                      {p.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="btn btn-primary"
                type="button"
                onClick={approve}
                disabled={busy !== "" || usableProviders.length === 0}
              >
                {busy === "approve" ? "Mengirim…" : `Setujui & antrikan ${plan.items?.length ?? 0} job`}
              </button>
              {usableProviders.length === 0 ? (
                <span className="muted small">
                  Tidak ada provider aktif — <Link to="/models">aktifkan di Model &amp; Backend</Link>.
                </span>
              ) : null}
              <button className="btn btn-danger" type="button" onClick={() => deletePlan(plan.id)}>
                Hapus draft
              </button>
            </div>
          ) : null}
          <div className="gc-actions">
            <button className="btn" type="button" onClick={reset}>
              {plan.status === "approved" ? "Buat rencana baru" : "Kembali ke form"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function PlanItemResult({ jobId }: { jobId: string }) {
  const [assetIds, setAssetIds] = useState<string[]>([]);
  const [previewId, setPreviewId] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    api
      .job(jobId)
      .then((job) => {
        if (!cancelled) setAssetIds(job.result_asset_ids);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [jobId]);
  if (assetIds.length === 0) return null;
  return (
    <div className="asset-grid">
      {assetIds.map((assetId) => (
        <figure key={assetId} className="asset-card">
          <button
            type="button"
            className="asset-open"
            onClick={() => setPreviewId(assetId)}
            title="Buka pratinjau"
          >
            <img src={assetFileUrl(assetId)} alt={assetId} loading="lazy" />
            <span className="asset-open-hint">Pratinjau</span>
          </button>
          <figcaption>
            <Link to="/projects">kelola di Projects →</Link>
          </figcaption>
        </figure>
      ))}
      {previewId ? <AssetPreview assetId={previewId} onClose={() => setPreviewId(null)} /> : null}
    </div>
  );
}
