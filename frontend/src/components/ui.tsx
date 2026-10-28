export type PillTone = "ok" | "warn" | "fail" | "neutral";

export function StatusPill({ tone, children }: { tone: PillTone; children: React.ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export function EmptyState({
  title,
  detail,
  hint,
}: {
  title: string;
  detail?: string;
  hint?: string;
}) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      {detail ? <p>{detail}</p> : null}
      {hint ? <p className="empty-hint">{hint}</p> : null}
    </div>
  );
}

export interface CheckRowLike {
  ok?: boolean;
  version?: string;
  free_gb?: number;
  available_gb?: number;
  types?: string[];
}

export function CheckRow({ label, check }: { label: string; check: CheckRowLike | undefined }) {
  const tone: PillTone = check?.ok ? "ok" : check?.types?.includes("model_missing") ? "warn" : "fail";
  let text = check?.ok ? "OK" : "Not ready";
  if (check?.version) text = String(check.version);
  if (check?.free_gb !== undefined) text = `${check.free_gb} GB free`;
  if (check?.available_gb !== undefined) text = `${check.available_gb} GB free`;
  return (
    <div className="check-row">
      <span>{label}</span>
      <StatusPill tone={tone}>{text}</StatusPill>
    </div>
  );
}
