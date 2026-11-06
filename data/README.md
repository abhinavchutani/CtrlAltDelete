# Data (local only, never committed)

Everything in this folder except this README is gitignored.

## Setup

Unzip the challenge pack here so that this path exists:

```
data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026/START_HERE.md
```

The pack ships as `APETIT_CLIMATE_NATURE_NAVIGATOR_2026.zip`, inside the `Apetit_SinceAI2026` download from the challenge. For example:

```bash
unzip ~/Downloads/Apetit_SinceAI2026/APETIT_CLIMATE_NATURE_NAVIGATOR_2026.zip -d data/
```

Code should read the location from `DATA_DIR` (see `.env.example`). It defaults to `./data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026`.

## Why it isn't in git

- **Size:** about 100 MB, and the source zip we submit must be under 100 MB without data files.
- **Licences:** the pack's data is CC BY 4.0, but `data/00_apetit_original/` is Apetit's workbook, shared for the hackathon only and **not** CC BY.
- **It's synthetic:** results must never be presented as Apetit's real emissions or as facts about real farms.
