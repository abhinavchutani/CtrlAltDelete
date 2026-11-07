import { useHealth } from "../api/hooks";

/** Always visible (V2 rule 8). */
export function SyntheticBanner() {
  const health = useHealth();
  return (
    <div className="banner" role="note">
      Synthetic data: not Apetit's real figures, not facts about real farms. Futures are one plausible weather path.
      {health.data?.mock ? " · MOCK fixtures (API_MOCK=1)" : ""}
      {health.error ? " · API not reachable" : ""}
    </div>
  );
}
