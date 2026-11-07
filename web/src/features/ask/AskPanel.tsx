import { useAsk, useRetrievalIsFixture } from "../../api/hooks";
import type { ReportRef, Table } from "../../api/types";
import { useStore } from "../../state/store";
import { Panel, Status } from "../../components/Status";
import { EvidenceChips } from "./EvidenceChips";
import { ReportButton } from "./ReportButton";
import { ResultTable } from "./ResultTable";

/** Retrieval answers (src.r_agent in real mode). */
export function AskPanel() {
  const question = useStore((s) => s.question);
  const history = useStore((s) => s.askHistory);
  const ask = useAsk(question, history);
  const a = ask.data;
  const fixture = useRetrievalIsFixture("ask");
  return (
    <Panel title="Ask">
      {fixture ? <p className="small sev-notable">Fixture rows (illustrative): this retrieval module is not built yet.</p> : null}
      {question ? <p className="muted">Q: {question}</p> : <p className="muted">Ask about the past: deliveries, energy, farms, rules.</p>}
      <Status loading={ask.isLoading} error={ask.error} />
      {a ? (
        <div>
          {a.status === "not_in_data" ? <strong>Not in the data</strong> : null}
          <p>{a.answer_md}</p>
          <ResultTable table={a.table as Table | null} />
          <EvidenceChips evidence={a.evidence} />
          <ReportButton report={a.report as ReportRef | null} />
          {a.pending_approval ? <p className="small">Uses draft results pending expert approval.</p> : null}
        </div>
      ) : null}
    </Panel>
  );
}
