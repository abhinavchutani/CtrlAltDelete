"""Track A pipeline entry point (`make a`). Steps are added as tasks land:

#7  farm survey + registry detectors → clean_farm_survey / clean_farm_registry   (src/a_clean.py)
#8–#9 remaining detectors, #11 inventory, #12 2025 CSVs + peat — to follow.
"""
from __future__ import annotations

from src import a_clean


def main() -> None:
    a_clean.main()


if __name__ == "__main__":
    main()
