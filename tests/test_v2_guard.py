"""v1 is frozen: every out/*_submission.csv must match out/v1_manifest.json byte for byte (sha256)."""
import json

from src import v1_manifest as M


def test_v1_submission_csvs_unchanged():
    want = json.loads(M.MANIFEST.read_text())
    have = M.digests()
    assert set(have) == set(want), f"submission CSV set changed: {sorted(set(have) ^ set(want))}"
    changed = [k for k in want if have[k] != want[k]]
    assert not changed, f"v1 CSVs changed (needs a human-approved v1 task): {changed}"
