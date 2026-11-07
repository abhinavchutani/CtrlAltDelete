// The one loading / error / empty renderer every panel uses.
export function Status({ loading, error, empty, emptyText = "Nothing to show." }: {
  loading?: boolean; error?: unknown; empty?: boolean; emptyText?: string;
}) {
  if (loading) return <span className="muted">Loading…</span>;
  if (error) return <span className="sev-critical" role="alert">{error instanceof Error ? error.message : String(error)}</span>;
  if (empty) return <span className="muted">{emptyText}</span>;
  return null;
}

export function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel" aria-label={title}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}
