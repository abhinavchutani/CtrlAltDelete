"""Track A pipeline entry point (`make a`). Steps are added as tasks land:

#7  farm survey + registry detectors → clean_farm_survey / clean_farm_registry   (src/a_clean.py)
#8–#9 remaining detectors · #10 LLM triage · #11 inventory · #12 2025 CSVs, corrections log, peat reveal
"""
from __future__ import annotations

from src import a_clean, a_export, a_inventory, a_triage


def main() -> None:
    a_clean.main()
    a_triage.main()      # grey-zone LLM triage (offline stub without a key)
    a_inventory.main()   # 2023–25 inventory + lineage, A2 dev scores
    a_export.main()      # 2025 A1 + A2 CSVs, corrections.csv, peat reveal


if __name__ == "__main__":
    main()
