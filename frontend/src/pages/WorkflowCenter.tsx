import { useEffect, useState } from "react";
import { api } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { EmptyState, StatusPill } from "../components/ui";
import type { Campaign, CreationPlan, Storyboard, Workflow, WorkflowStep } from "../types/api";

const KIND_LABELS: Record<string, string> = {
  generate_plan: "Generate (approve plan)",
  render_storyboard: "Render animatic",
  export_campaign: "Export campaign",
  manual_check: "Manual check",
};

function stepTone(status: string): "ok" | "warn" | "fail" | "neutral" {
  if (status === "done") return "ok";
  if (status === "failed") return "fail";
  if (status === "skipped") return "warn";
  return "neutral";
}

export function WorkflowCenter() {
  const meta = useApiState(() => api.workflowMeta(), []);
  const plans = useApiState<{ items: CreationPlan[] }>(() => api.plans({}), []);
  const storyboards = useApiState<{ items: Storyboard[] }>(() => api.storyboards({}), []);
  const campaigns = useApiState<{ items: Campaign[] }>(() => api.campaigns({}), []);
  const providers = useApiState<{ items: { provider_id: string; display_name: string; enabled: boolean; health: { ok: boolean } }[] }>(
    () => api.providers(),
    []
  );
  const [listKey, setListKey] = useState(0);
  const workflows = useApiState<{ items: Workflow[] }>(() => api.workflows({}), [listKey]);
  const [open, setOpen] = useState<Workflow | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [stepKind, setStepKind] = useState("generate_plan");
  const [refId, setRefId] = useState("");
  const [providerId, setProviderId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const usableProviders = (providers.data?.items ?? []).filter((p) => p.enabled && p.health.ok);
  useEffect(() => {
    if (!providers.data || providerId) return;
    const usable = providers.data.items.find((p) => p.enabled && p.health.ok);
    if (usable) setProviderId(usable.provider_id);
  }, [providers.data, providerId]);

  const refresh = () => setListKey((k) => k + 1);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      setOpen(await api.createWorkflow({ name: name.trim() }));
      setCreating(false);
      setName("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuat workflow");
    }
  };

  const openWf = async (id: string) => {
    try {
      setOpen(await api.workflow(id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal membuka workflow");
    }
  };

  const refOptions = () => {
    if (stepKind === "generate_plan")
      return (plans.data?.items ?? []).filter((p) => p.status === "draft").map((p) => ({ id: p.id, label: p.title || p.id }));
    if (stepKind === "render_storyboard")
      return (storyboards.data?.items ?? []).map((s) => ({ id: s.id, label: `${s.title} (${s.scene_count ?? 0} scene)` }));
    if (stepKind === "export_campaign")
      return (campaigns.data?.items ?? []).map((c) => ({ id: c.id, label: `${c.name} (${c.asset_count ?? 0} aset)` }));
    return [];
  };

  const addStep = async () => {
    if (!open || busy) return;
    const needsRef = stepKind !== "manual_check";
    if (needsRef && !refId) return;
    setBusy(true);
    try {
      setOpen(await api.addWorkflowStep(open.id, { kind: stepKind, ref_id: needsRef ? refId : null }));
      setRefId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menambah step");
    } finally {
      setBusy(false);
    }
  };

  const runStep = async (step: WorkflowStep) => {
    if (!open || busy) return;
    if (step.kind === "generate_plan") {
      const planProvider = usableProviders[0];
      if (!planProvider || !window.confirm(`Step ini akan mengirim prompt ke provider "${planProvider.display_name}" dan membuat job generation. Lanjutkan?`))
        return;
    }
    setBusy(true);
    try {
      setOpen(await api.runWorkflowStep(open.id, step.id, step.kind === "generate_plan" ? providerId : null));
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menjalankan step");
    } finally {
      setBusy(false);
    }
  };

  const stepAction = async (step: WorkflowStep, action: "skip" | "retry" | "remove") => {
    if (!open || busy) return;
    setBusy(true);
    try {
      if (action === "skip") setOpen(await api.skipWorkflowStep(open.id, step.id));
      else if (action === "retry") setOpen(await api.retryWorkflowStep(open.id, step.id));
      else setOpen(await api.removeWorkflowStep(open.id, step.id));
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal memproses step");
    } finally {
      setBusy(false);
    }
  };

  const removeWf = async (id: string) => {
    if (!window.confirm("Hapus workflow ini?")) return;
    try {
      await api.deleteWorkflow(id);
      if (open?.id === id) setOpen(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menghapus workflow");
    }
  };

  if (meta.loading) return <div className="page-loading">Loading…</div>;
  const kinds = meta.data?.step_kinds ?? [];
  const nextStep = open?.steps?.find((s) => s.status === "pending" || s.status === "failed");

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Workflow Center</h1>
          <p>Pipeline berurutan atas modul yang ada: generate → render → export, dengan checkpoint manual.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating((c) => !c)}>
          {creating ? "Tutup" : "+ Workflow baru"}
        </button>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {creating ? (
        <form className="panel create-form" onSubmit={create}>
          <label>
            Nama workflow
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="mis. Launch Kopi End-to-End" />
          </label>
          <button className="btn btn-primary" type="submit">
            Buat workflow
          </button>
        </form>
      ) : null}

      {open ? (
        <section className="panel">
          <div className="panel-head">
            <h2>
              {open.name} <span className="muted small">({open.id})</span>
            </h2>
            <StatusPill tone={open.status === "done" ? "ok" : "neutral"}>{open.status}</StatusPill>
          </div>

          {open.steps && open.steps.length > 0 ? (
            <div className="scene-list">
              {open.steps.map((step, index) => (
                <div key={step.id} className="scene-row wf-step">
                  <div className="wf-step-num">{index + 1}</div>
                  <div className="scene-info">
                    <div className="list-title">
                      {step.title} <span className="muted small">• {KIND_LABELS[step.kind] ?? step.kind}</span>
                    </div>
                    <div className="muted small">
                      {step.ref_summary ? `${step.ref_summary.title} — ${step.ref_summary.status}` : "—"}
                      {step.note ? ` • ${step.note}` : ""}
                    </div>
                    {step.result?.job_ids ? (
                      <div className="muted small">job dikirim: {(step.result.job_ids as string[]).length}</div>
                    ) : null}
                    {step.result?.output_asset_id ? (
                      <div className="muted small">video asset: {String(step.result.output_asset_id)}</div>
                    ) : null}
                    {step.result?.filename ? (
                      <div className="muted small">paket: {String(step.result.filename)}</div>
                    ) : null}
                  </div>
                  <div className="plan-item-status">
                    <StatusPill tone={stepTone(step.status)}>{step.status}</StatusPill>
                  </div>
                  <div className="scene-actions">
                    {step.status === "pending" && nextStep?.id === step.id ? (
                      <button className="btn btn-primary" type="button" disabled={busy} onClick={() => runStep(step)}>
                        Jalankan
                      </button>
                    ) : null}
                    {step.status === "failed" && nextStep?.id === step.id ? (
                      <button className="btn" type="button" disabled={busy} onClick={() => stepAction(step, "retry")}>
                        Retry
                      </button>
                    ) : null}
                    {step.status === "pending" ? (
                      <button className="btn" type="button" disabled={busy} onClick={() => stepAction(step, "skip")}>
                        Skip
                      </button>
                    ) : null}
                    <button className="btn btn-danger" type="button" disabled={busy} onClick={() => stepAction(step, "remove")}>
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="Workflow kosong" detail="Tambahkan step: generate, render, export, atau manual check." />
          )}

          <div className="gc-approve">
            <label>
              Jenis step
              <select value={stepKind} onChange={(e) => { setStepKind(e.target.value); setRefId(""); }}>
                {kinds.map((k) => (
                  <option key={k.kind} value={k.kind}>
                    {KIND_LABELS[k.kind] ?? k.kind}
                  </option>
                ))}
              </select>
            </label>
            {stepKind !== "manual_check" ? (
              <label>
                Referensi
                <select value={refId} onChange={(e) => setRefId(e.target.value)}>
                  <option value="">— pilih —</option>
                  {refOptions().map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {stepKind === "generate_plan" ? (
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
            ) : null}
            <button
              className="btn btn-primary"
              type="button"
              onClick={addStep}
              disabled={busy || (stepKind !== "manual_check" && !refId)}
            >
              + Tambah step
            </button>
          </div>

          <div className="gc-actions" style={{ marginTop: 12 }}>
            <button className="btn" type="button" onClick={() => { setOpen(null); refresh(); }}>
              Tutup editor
            </button>
            <button className="btn btn-danger" type="button" onClick={() => removeWf(open.id)}>
              Hapus workflow
            </button>
          </div>
        </section>
      ) : null}

      {workflows.data && workflows.data.items.length > 0 ? (
        <section className="panel">
          <div className="panel-head">
            <h2>Workflow tersimpan</h2>
          </div>
          <ul className="list">
            {workflows.data.items.map((w) => (
              <li key={w.id} className="list-row">
                <div>
                  <div className="list-title">{w.name}</div>
                  <div className="muted small">
                    {w.steps_finished}/{w.step_count} step selesai • {w.status} •{" "}
                    {new Date(w.created_at).toLocaleString("id-ID")}
                  </div>
                </div>
                <div className="plan-row-actions">
                  <button className="btn" type="button" onClick={() => openWf(w.id)}>
                    Buka
                  </button>
                  <button className="btn btn-danger" type="button" onClick={() => removeWf(w.id)}>
                    Hapus
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <EmptyState
          title="Belum ada workflow"
          detail="Workflow merangkai plan, storyboard, dan campaign menjadi pipeline berurutan."
        />
      )}
    </div>
  );
}
