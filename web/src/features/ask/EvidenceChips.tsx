import type { EvidenceRef } from "../../api/types";

export function EvidenceChips({ evidence }: { evidence: EvidenceRef[] }) {
  if (!evidence.length) return null;
  return (
    <div className="row" aria-label="evidence">
      {evidence.map((e) => <span key={`${e.kind}:${e.ref}`} className="chip" title={`${e.kind}: ${e.ref}`}>{e.label}</span>)}
    </div>
  );
}
