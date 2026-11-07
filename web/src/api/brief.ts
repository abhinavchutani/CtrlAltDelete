// The Overview's three-problem brief (GET /api/brief), the issue review list and the inventory report.
import { useMutation, useQuery } from "@tanstack/react-query";
import { get, post, qs } from "./client";

export type Count = { key: string; label: string; n: number };
export type Brief = {
  data: {
    feeds: number; records: number; records_checked: number; issues_found: number; legit_left_alone: number;
    issues_2025: number; awaiting_signoff: number; approved: number; by_source: Count[]; by_type: Count[];
    accuracy: { score: number; precision_pct: number; recall_pct: number } | null;
  };
  reports: {
    year: number; scope1: number; scope2_market: number; scope2_location: number; scope3: number; total_market: number;
    scope3_top: { key: string; t: number }[]; records_traced: number; trace_links: number; factors_used: number;
    dev_scores: { year: number; score: number }[];
    draft_checks: { line: string; draft: number; rebuilt: number; ratio: number }[];
    draft_total: number; draft_sum_of_parts: number;
  };
  sweden: {
    region: string; crop: string; year: number;
    months: { month: number; rain_anom_pct: number; temp_anom_c: number; hot_days: number }[];
    flowering_month: number; flowering_rain_pct: number | null; spring_rain_pct: number | null;
    signal_date: string; event: { date: string; label: string; source: string }; lead_days: number;
    predicted_t: number | null; actual_t: number | null; model_error_pct: number | null;
    drop_vs_prev_pct: number | null; fi_change_pct: number | null; bad_year_eur_p90: number | null;
  };
  synthetic: boolean;
};
export type IssueRow = {
  issue_id: string; table_name: string; record_key: string; year: number; issue_type: string; confidence: number;
  explanation: string; field: string | null; old_value: string | null; new_value: string | null;
  type_label: string; source_label: string; signed_off: boolean;
};
export type ReportRef = { report_id: string; filename: string; url: string };

export const useBrief = () => useQuery({ queryKey: ["brief"], queryFn: () => get<Brief>("/api/brief"), staleTime: Infinity });
export const useIssues = (status: "proposed" | "legitimate", source: string | null) =>
  useQuery({
    queryKey: ["issues", status, source],
    queryFn: () => get<IssueRow[]>(`/api/issues${qs({ status, source, limit: 60 })}`),
    staleTime: Infinity,
  });
export const useInventoryReport = () =>
  useMutation({ mutationFn: (year: number) => post<ReportRef>(`/api/report/inventory${qs({ year })}`, {}) });
