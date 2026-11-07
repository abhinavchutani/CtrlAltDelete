import type { Table } from "../../api/types";

export function ResultTable({ table }: { table: Table | null | undefined }) {
  if (!table?.columns?.length) return null;
  return (
    <table>
      <thead><tr>{table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{table.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{v ?? ""}</td>)}</tr>)}</tbody>
    </table>
  );
}
