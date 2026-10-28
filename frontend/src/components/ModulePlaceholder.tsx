import { EmptyState } from "./ui";

export function ModulePlaceholder({
  title,
  subtitle,
  inPlan,
}: {
  title: string;
  subtitle: string;
  inPlan: string;
}) {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
      </header>
      <EmptyState title="Modul ini belum diimplementasikan" detail={inPlan} />
    </div>
  );
}
