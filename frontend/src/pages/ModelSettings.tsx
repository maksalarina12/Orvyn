import { useState } from "react";
import { useApiState } from "../hooks/useApi";
import { api } from "../services/api";
import { CheckRow, EmptyState, StatusPill } from "../components/ui";
import type { ProviderStatus } from "../types/api";

function ProviderCard({ provider, reload }: { provider: ProviderStatus; reload: () => void }) {
  const schema = provider.capabilities.config_schema ?? [];
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const setField = (key: string, value: string) => setValues((v) => ({ ...v, [key]: value }));
  const filledConfig = () => {
    const cfg: Record<string, string> = {};
    for (const field of schema) {
      const value = (values[field.key] ?? "").trim();
      if (value) cfg[field.key] = value;
    }
    return Object.keys(cfg).length ? cfg : undefined;
  };
  const missingRequired = schema
    .filter(
      (f) => f.required && !(values[f.key] ?? "").trim() && provider.config_redacted?.[f.key] !== "<set>"
    )
    .map((f) => f.label);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      if (provider.enabled) {
        await api.enableProvider(provider.provider_id, { enable: false });
      } else {
        if (provider.is_external && missingRequired.length > 0) {
          setError(`Isi dulu: ${missingRequired.join(", ")}`);
          setBusy(false);
          return;
        }
        const ok = window.confirm(
          `Aktifkan "${provider.display_name}"?\n${
            provider.is_external
              ? "PERHATIAN: ini mengirim prompt/data ke layanan pihak ketiga (luar lokal). Data yang dikirim tidak lagi privat."
              : "Provider ini berjalan lokal."
          }`
        );
        if (!ok) {
          setBusy(false);
          return;
        }
        await api.enableProvider(provider.provider_id, {
          enable: true,
          confirmed_external: provider.is_external,
          config: filledConfig(),
        });
      }
      setValues({});
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengubah provider");
    } finally {
      setBusy(false);
    }
  };

  const saveCredentials = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.enableProvider(provider.provider_id, {
        enable: true,
        confirmed_external: provider.is_external,
        config: filledConfig(),
      });
      setValues({});
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan konfigurasi");
    } finally {
      setBusy(false);
    }
  };

  const redactedSet = (key: string) => provider.config_redacted?.[key] === "<set>";

  return (
    <article className="project-card">
      <div className="flex-between">
        <h3>{provider.display_name}</h3>
        <StatusPill tone={provider.enabled ? (provider.health.ok ? "ok" : "warn") : "neutral"}>
          {provider.enabled ? (provider.health.ok ? "AKTIF" : "AKTIF • belum siap") : "DISABLED"}
        </StatusPill>
      </div>
      <p className="muted small">
        {provider.is_external ? "External service (data dikirim ke pihak ketiga)" : "Local"} • modes:{" "}
        {provider.capabilities.modes.join(", ")}
      </p>
      <p className="muted small">{provider.health?.reason}</p>
      {provider.health?.space_url ? <p className="muted small">space: {provider.health.space_url}</p> : null}
      {provider.health?.model ? <p className="muted small">model: {provider.health.model}</p> : null}

      {schema.length > 0 ? (
        <div className="provider-config">
          {schema.map((field) => (
            <label key={field.key}>
              {field.label}
              <input
                type={field.secret ? "password" : "text"}
                value={values[field.key] ?? ""}
                onChange={(e) => setField(field.key, e.target.value)}
                placeholder={
                  redactedSet(field.key)
                    ? "<sudah diisi> — isi ulang untuk mengganti"
                    : field.required && !provider.enabled
                      ? "wajib untuk aktivasi"
                      : ""
                }
              />
            </label>
          ))}
          {provider.enabled ? (
            <button className="btn" disabled={busy || Object.keys(filledConfig() ?? {}).length === 0} onClick={saveCredentials}>
              Simpan kredensial
            </button>
          ) : null}
          {!provider.enabled && provider.is_external ? (
            <p className="muted small">
              Aktivasi melakukan probe nyata ke layanan untuk memvalidasi kredensial/endpoint sebelum dipakai.
            </p>
          ) : null}
        </div>
      ) : null}

      {error ? <div className="error-banner">{error}</div> : null}
      <button className={`btn ${provider.enabled ? "btn-danger" : "btn-primary"}`} disabled={busy} onClick={toggle}>
        {provider.enabled ? "Nonaktifkan" : "Aktifkan (butuh konfirmasi)"}
      </button>
    </article>
  );
}

export function ModelSettings() {
  const [reloadKey, setReloadKey] = useState(0);
  const providers = useApiState<{ items: ProviderStatus[] }>(() => api.providers(), [reloadKey]);
  const health = useApiState(() => api.health(), [reloadKey]);
  const reload = () => setReloadKey((k) => k + 1);

  if (providers.loading) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Model &amp; Backend Settings</h1>
          <p>Nyata: provider eksternal disabled by default; aktivasi memerlukan konfirmasi sadar per provider.</p>
        </div>
      </header>

      <div className="grid-cards">
        {(providers.data?.items ?? []).map((p) => (
          <ProviderCard key={p.provider_id} provider={p} reload={reload} />
        ))}
      </div>

      <section className="panel">
        <h2>System runtime</h2>
        {health.data ? (
          <>
            <CheckRow label="FFmpeg (video assembly lokal)" check={health.data.checks.ffmpeg} />
            <CheckRow label="Disk bebas" check={health.data.checks.storage} />
            <CheckRow label="RAM tersedia" check={health.data.checks.memory} />
            <CheckRow label="Database" check={health.data.checks.database} />
          </>
        ) : (
          <EmptyState title="Health check gagal" detail={health.error ?? undefined} />
        )}
      </section>
    </div>
  );
}
