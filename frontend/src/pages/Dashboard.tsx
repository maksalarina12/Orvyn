import { useState } from "react";
import type { Health, Asset, GenerationJob, Project } from "../types/api";
import { api, assetFileUrl } from "../services/api";
import { useApiState } from "../hooks/useApi";
import { CheckRow, EmptyState, StatusPill } from "../components/ui";
import { AssetPreview } from "../components/AssetPreview";
import { Link } from "react-router-dom";

const JOB_TONE: Record<GenerationJob["status"], "ok" | "warn" | "fail" | "neutral"> = {
  completed: "ok",
  running: "warn",
  queued: "neutral",
  failed: "fail",
  cancelled: "neutral",
};

function SectionHead({ index, title, to, linkLabel }: { index: string; title: string; to?: string; linkLabel?: string }) {
  return (
    <div className="sec-head">
      <span className="sec-index">{index}</span>
      <h2>{title}</h2>
      <span className="sec-rule" />
      {to ? <Link to={to}>{linkLabel ?? "buka →"}</Link> : null}
    </div>
  );
}

function timeLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function Dashboard() {
  const health = useApiState<Health>(() => api.health(), []);
  const projects = useApiState<{ items: Project[] }>(() => api.projects({}), []);
  const assets = useApiState<{ items: Asset[] }>(() => api.assets({ limit: 10 }), []);
  const jobs = useApiState<{ items: GenerationJob[] }>(() => api.jobs({ limit: 6 }), []);
  const [previewId, setPreviewId] = useState<string | null>(null);

  if (health.loading) return <div className="page-loading">Loading…</div>;
  if (health.error || !health.data)
    return (
      <EmptyState
        title="Backend API tidak dapat dihubungi"
        detail={health.error ?? undefined}
        hint="Pastikan backend berjalan: scripts/start.sh"
      />
    );

  const h = health.data;
  const inference = h.checks.inference_backend;
  const storage = h.checks.storage;
  const memory = h.checks.memory;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <div className="kicker">CONSOLE / RINGKASAN</div>
          <h1>Dashboard</h1>
          <p>Status sistem dan log kerja — semua angka dibaca langsung dari backend lokal.</p>
        </div>
        <StatusPill tone={h.status === "ok" ? "ok" : h.status === "degraded" ? "warn" : "fail"}>
          {h.status.toUpperCase()}
        </StatusPill>
      </header>

      <div className="board-grid">
        <section className="panel">
          <SectionHead index="01" title="SYSTEM CHECK" />
          <CheckRow label="Database (SQLite)" check={h.checks.database} />
          <CheckRow label="FFmpeg" check={h.checks.ffmpeg} />
          <CheckRow label="Disk / [data]" check={storage} />
          <CheckRow label="RAM available" check={memory} />
          <CheckRow label="Inference backend" check={inference} />
          <div className="readout-row">
            <span className="readout-label">APP</span>
            <span className="readout-value">v{h.app_version}</span>
            <span className="readout-label">HOST</span>
            <span className="readout-value">{h.host}</span>
          </div>
          {!inference.ok ? (
            <p className="muted small">
              {inference.reason} — generation lewat provider eksternal tetap bisa jalan.{" "}
              <Link to="/models">Model &amp; Backend →</Link>
            </p>
          ) : null}
        </section>

        <section className="panel">
          <SectionHead index="02" title="MULAI KERJA" />
          <div className="quick-grid">
            <Link to="/quick-generate" className="quick-link">
              <span className="quick-index">02</span>
              <span className="quick-title">Quick Generate</span>
              <span className="quick-note">gambar / video langsung</span>
            </Link>
            <Link to="/guided-creation" className="quick-link">
              <span className="quick-index">03</span>
              <span className="quick-title">Guided Creation</span>
              <span className="quick-note">rencana multi-angle</span>
            </Link>
            <Link to="/remix-improve" className="quick-link">
              <span className="quick-index">06</span>
              <span className="quick-title">Remix &amp; Improve</span>
              <span className="quick-note">revisi dari aset</span>
            </Link>
            <Link to="/workflows" className="quick-link">
              <span className="quick-index">08</span>
              <span className="quick-title">Workflow Center</span>
              <span className="quick-note">rantai langkah</span>
            </Link>
          </div>
          <div className="readout-row">
            <span className="readout-label">PROYEK</span>
            <span className="readout-value mono-num">{projects.data?.items.length ?? "—"}</span>
            <span className="readout-label">ASET</span>
            <span className="readout-value mono-num">{assets.data?.items.length ?? "—"}</span>
            <span className="readout-label">JOB</span>
            <span className="readout-value mono-num">{jobs.data?.items.length ?? "—"}</span>
          </div>
          <div className="tip-line">
            <kbd>⌘K</kbd> cari &amp; perintah
            <span className="tip-sep">·</span>
            <kbd>1–9</kbd> lompat halaman
            <span className="tip-sep">·</span>
            <kbd>?</kbd> pintasan
          </div>
        </section>
      </div>

      <section className="panel">
        <SectionHead index="03" title="JOB TERAKHIR" to="/quick-generate" linkLabel="antre baru →" />
        {jobs.loading ? (
          <div className="muted">Memuat…</div>
        ) : jobs.data && jobs.data.items.length > 0 ? (
          <ul className="job-list">
            {jobs.data.items.map((j) => (
              <li key={j.id} className="job-row">
                <StatusPill tone={JOB_TONE[j.status]}>{j.status}</StatusPill>
                <code className="job-id">{j.id}</code>
                <span className="job-mode">{j.mode.replace(/_/g, " ")}</span>
                <span className="job-provider">{j.provider_id}</span>
                <span className="job-time">{timeLabel(j.created_at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="Belum ada job" detail="Kirim prompt pertama dari Quick Generate untuk mengisi log ini." />
        )}
      </section>

      <section className="panel">
        <SectionHead index="04" title="OUTPUT TERBARU" to="/projects" linkLabel="library →" />
        {assets.data && assets.data.items.length > 0 ? (
          <div className="filmstrip">
            {assets.data.items.map((a) => (
              <button
                key={a.id}
                type="button"
                className="film-frame"
                title={`Pratinjau ${a.filename}`}
                onClick={() => setPreviewId(a.id)}
              >
                {a.file_type === "image" ? (
                  <img src={assetFileUrl(a.id)} alt={a.filename} loading="lazy" />
                ) : (
                  <span className="film-video">▶ VIDEO</span>
                )}
                <span className="film-cap">
                  <span>{a.width && a.height ? `${a.width}×${a.height}` : a.file_type.toUpperCase()}</span>
                  <code>{a.id.slice(-6)}</code>
                </span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Belum ada aset"
            detail="Hasil generation dan unggahan muncul di sini setelah provider aktif."
          />
        )}
      </section>

      <section className="panel">
        <SectionHead index="05" title="PROYEK" to="/projects" linkLabel="kelola →" />
        {projects.loading ? (
          <div className="muted">Memuat…</div>
        ) : projects.data && projects.data.items.length > 0 ? (
          <ul className="list">
            {projects.data.items.slice(0, 5).map((p) => (
              <li key={p.id} className="list-row">
                <Link to="/projects" className="list-title">
                  {p.name}
                </Link>
                <span className="muted small mono-num">
                  {p.category.replace(/_/g, " ")} · {p.asset_count} aset
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="Belum ada proyek" detail="Buat proyek pertama di halaman Projects & Assets." />
        )}
      </section>
      {previewId ? <AssetPreview assetId={previewId} onClose={() => setPreviewId(null)} /> : null}
    </div>
  );
}
