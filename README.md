# IDGeneratorPy

A command-line tool for generating and managing randomized participant IDs in clinical or epidemiological studies. Cross-platform Python port of [idGenerator](https://github.com/mpmky/idGenerator) (Olden et al. 2016, University of Regensburg).

Each participant receives three linked IDs — a personal ID (IDP), a study data ID (IDS), and a temporary linkage key (IDT) — drawn from separate random number pools. Deleting the IDT column severs the link between personal and study data entirely, enabling full anonymisation without losing the scientific dataset.

The script is designed around two common scenarios:

**Starting a new study** — you have a planned sample size and want to assign IDs as participants are recruited. IDs are generated in batches, either by specifying counts directly on the command line or from an input sheet. When new recruits join in a later wave, you run the same command with the additional counts and the script extends existing records automatically, guaranteeing no ID is ever reused.

**Assigning IDs to an existing cohort** — participants are already enrolled and you need uniform trackable IDs for data linkage. You provide the current cohort size once and generate IDs for everyone. New recruits added later are handled the same way as the scenario above.

In both cases, study parameters are saved once with `init` and reused automatically on every subsequent run. All output is logged and the full ID state is always recoverable from the files on disk.

> For the ID system design, all command flags, and a detailed multi-wave worked example, see [REFERENCE.md](REFERENCE.md).  
> For a full list of changes and new features relative to the original VB.NET programme, see [CHANGES.md](CHANGES.md).

---

## Requirements

- Python 3.7 or later
- No third-party packages required for `.txt` / `.csv` / `.tsv` input
- Excel input (`.xlsx`): `pip install openpyxl`

---

## Setup

### 1. Install

```bash
git clone https://github.com/kaiyao28/IDGeneratorPy.git
cd IDGeneratorPy
```

### 2. Save study parameters once

Run `init` at the start of your project. It writes a `study.cfg` file that every subsequent command loads automatically — you will not need to repeat these settings.

```bash
python3 idgenerator.py init \
    --study   MyStudy \
    --center  01 \
    --output  ./ids
```

`--center` is your coordinating site code. All other settings use sensible defaults (`--digits 5`, `--blocks CTNVX`, `--checksum Damm_2004`, `--case-prefix S`, `--control-prefix C`, `--visit 2`). Override any of them here if needed.

Two flags to set if your cohort collects multiple data types (genetics, phenotyping, imaging…):

- **`--tracks Genetics,Phenotype`** — declares the data tracks once; every subsequent `batch` call loads this list automatically.
- **`--anon`** — marks the cohort as anonymised (IDS pool used, no IDP generated). Use this for Scenario 2.

> For a full explanation of `--blocks` letter options, `--digits` capacity limits, and planning guidance, see [REFERENCE.md](REFERENCE.md).

---

## Scenario 1 — Single cohort, specifying counts directly

Use this when your study has one cohort and you want to assign IDs without creating an input file. Run `init` once to save your settings, then pass participant counts directly on the command line with `--samplesize`.

**Step 1 — init** (set `--blocks` here, not on every batch call):

```bash
# No case/control distinction
python3 idgenerator.py init \
    --study  MyStudy \
    --center 01 \
    --blocks CTNVX \
    --output ./ids

# With cases and controls
python3 idgenerator.py init \
    --study  MyStudy \
    --center 01 \
    --blocks CTGNVX \
    --output ./ids
```

**Step 2 — generate IDs** (one number = total N; two numbers = NCases NControls):

```bash
# No case/control distinction
python3 idgenerator.py batch \
    --samplesize 5000 \
    --output ./ids

# With cases and controls
python3 idgenerator.py batch \
    --samplesize 50 80 \
    --output ./ids
```

The track name defaults to the study name (set in `init`). To use a different name, add `--track MyCohort`.

Output files are written to `./ids/`:

```
ids/
  YYYYMMDD_MyStudy_IDP_IDT_ALL_N=130.txt   ← personal data + temp keys
  YYYYMMDD_MyStudy_IDS_IDT_ALL_N=130.txt   ← study data + temp keys
  per_site/                                 ← individual files per group
  LogFile.txt
  study.cfg
```

**Adding new recruits in a later wave** — run the same command with the *additional* count. The script detects the existing cohort automatically and extends it:

```bash
python3 idgenerator.py batch \
    --samplesize 10 20 \
    --blocks CTGNVX \
    --output ./ids
```

Old per-site files are renamed `.old`. The master files are rebuilt to include the full cohort.

---

## Scenario 2 — Multi-track anonymised cohort across sites

> **Before running any batch command, make sure you have run `init` once** (see Setup above) with `--tracks` and `--anon` set.

Use this when participants are already anonymised and you need separate, independent ID sets for different data types — genetics, phenotyping, imaging, and so on. Because there is no personal data to track, only IDS (study data IDs) are generated — no IDP. The IDT linkage key connects the data types across tracks; delete it once labelling is complete to fully sever that link.

Each data type is a **track**. Tracks are declared once at `init` and saved to `study.cfg` — you do not repeat them on every `batch` call. **Declare all tracks you will need before the first batch run** — tracks cannot be added retroactively to existing participants. See [REFERENCE.md](REFERENCE.md) and [test_scenario2/commands.sh](test_scenario2/commands.sh) for guidance on starting a new parallel dataset if a track is added later.

**Step 1 — save study parameters, declare tracks, mark as anonymised:**

```bash
python3 idgenerator.py init \
    --study    AnonymCohort \
    --center   01 \
    --blocks   CTGNVX \
    --tracks   Genetics \
    --anon \
    --output   ./ids
```

**Step 2 — prepare the site sheet (`wave1.txt`):**

```
SampleName   NCases   NControls
SiteA        200      0
SiteB        150      75
```

Each row is a site. `NCases` is the participant count. `NControls` is used for sites with a case/control split; set to `0` otherwise.

**Step 3 — generate IDs for Wave 1:**

```bash
python3 idgenerator.py batch \
    --input-file wave1.txt \
    --output ./ids \
    --seed 10
```

`--tracks` and `--anon` are loaded from `study.cfg` automatically. Every participant receives one IDT and one IDS per track.

Output:

```
ids/
  YYYYMMDD_AnonymCohort_IDS_T=Genetics_ALL_N=425.txt   ← all sites combined
  per_site/
    YYYYMMDD_AnonymCohort_IDS_T=Genetics_SITE=SiteA_N=200_Baseline.txt
    YYYYMMDD_AnonymCohort_IDS_T=Genetics_SITE=SiteB_N=225_Baseline.txt
```

Per-site columns: `IDT | IDS_Genetics`  
Master ALL columns: `Site | IDT | IDS_Genetics`

**Adding participants in a later wave** — provide a new sheet with the *additional* counts:

```bash
python3 idgenerator.py batch \
    --input-file wave2.txt \
    --output ./ids \
    --seed 11
```

Old per-site files are renamed `.old` and the master ALL is rebuilt.

---

## Follow-up visits

Once baseline IDs have been generated, a single command produces follow-up visit IDs for all sites. No input file is needed — the script reads the IDS files it already wrote to `ids/per_site/` automatically.

Each follow-up ID is the baseline IDS ID with a visit prefix prepended:

```
Baseline IDS  :  01SiteAS123451X
Visit 2 IDSV2 :  V2_01SiteAS123451X
Visit 3 IDSV3 :  V3_01SiteAS123451X
```

This makes it impossible to confuse a visit 2 sample with a baseline sample — the `V2_` prefix is immediately visible on the tube label or in a spreadsheet. The full baseline ID is embedded so the link is always traceable. No new random numbers are drawn; all visit IDs are derived from the existing baseline.

The visit number comes from `study.cfg` (the `--visit` value you set in `init`). The default is `2`.

```bash
python3 idgenerator.py followup --output ./ids
```

Output:

```
ids/
  YYYYMMDD_MyStudy_IDS_IDSV2_ALL_N=240_V=2.txt   ← all sites, IDS + IDSV2 pairs
  followup/
    YYYYMMDD_MyStudy_IDS_IDSV2_T=SiteA_…_V=2.txt ← per-site files
```

Per-site files have columns `IDS | IDSV2 | IDS128 | IDSV2128` — baseline and visit IDs side by side with their barcodes, for tube label printing. The master ALL file has `IDS | IDSV2 | Track | Group` — no barcode columns, clean for Excel/R analysis.

To generate a different visit number without changing `study.cfg`:

```bash
python3 idgenerator.py followup --visit 3 --output ./ids
```

Visit numbers can be any integer ≥ 2. There is no upper limit.

---

## Output files at a glance

| File | Location | Who uses it |
|------|----------|-------------|
| `IDP_IDT_ALL_N=….txt` | `ids/` | Your team — personal data + temp keys. Keep confidential. |
| `IDS_IDT_ALL_N=….txt` | `ids/` | Analysts — study data + temp keys. |
| `IDS_IDSV{n}_ALL_…txt` | `ids/` | Analysts — baseline IDS paired with follow-up IDS. |
| `IDS_T=…_ALL_N=….txt` | `ids/` | Multi-track anonymised cohort master — Site + IDT + one IDS column per track. |
| Per-site `IDP_IDT_T=…` | `ids/per_site/` | Reference copy per site/group (standard batch). |
| Per-site `IDS_T=…_SITE=…` | `ids/per_site/` | Reference copy per site (multi-track anonymised batch). |
| `LogFile.txt` | `ids/` | Full audit trail. |

The `_Baseline` suffix marks files created in the first run for a site; `_Extended` marks files after subjects were added.

---

## Credits

> Olden M, Holle R, Heid IM, Stark K.  
> *IDGenerator: unique identifier generator for epidemiologic or clinical studies.*  
> BMC Medical Research Methodology. 2016;16(1):103.  
> DOI: [10.1186/s12874-016-0222-3](https://doi.org/10.1186/s12874-016-0222-3)

Source: [osf.io/urs2g](https://osf.io/urs2g/) — Genetic Epidemiology, University of Regensburg.  
Python adaptation: kaiyao28
