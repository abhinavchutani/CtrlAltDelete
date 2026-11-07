import type { ReportRef } from "../../api/types";

export function ReportButton({ report }: { report: ReportRef | null | undefined }) {
  if (!report) return null;
  return <a href={report.url} download={report.filename}>Download {report.filename}</a>;
}
