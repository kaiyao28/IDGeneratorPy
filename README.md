# IDGeneratorPy

A command-line tool for generating and managing randomized participant IDs in clinical or epidemiological studies. Cross-platform Python port of [idGenerator](https://github.com/mpmky/idGenerator) (Olden et al. 2016, University of Regensburg).

Each participant receives three linked IDs — a personal ID (IDP), a study data ID (IDS), and a temporary linkage key (IDT) — drawn from separate random number pools. Deleting the IDT column severs the link between personal and study data entirely, enabling full anonymisation without losing the scientific dataset.

The script is designed around two common scenarios:

**Starting a new study** — you have a planned sample size and want to assign IDs as participants are recruited. IDs are generated in batches from a simple input sheet. When new recruits join in a later wave, you run the same command with the additional counts and the script extends existing records automatically, guaranteeing no ID is ever reused.

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

`--center` is your coordinating site code. All other settings use sensible defaults (`--digits 5`, `--blocks CTGNVX`, `--checksum Damm_2004`, `--case-prefix S`, `--control-prefix C`, `--visit 2`). Override any of them here if needed.

**Choosing `--digits`** — the digit count determines the maximum number of **enrolled participants** your study can have in total across all recruitment waves. The available range is split equally across three ID pools (IDP / IDS / IDT), so the limit is roughly one third of the total range:

| `--digits` | Max enrolled participants |
|-----------|--------------------------|
| `5` (default) | ~30,000 |
| `6` | ~300,000 |
| `7` | ~3,000,000 |

**Follow-up visits do not consume pool numbers.** The `followup` command derives visit IDs from the same N value used at baseline — only the visit digit changes (`V=1` → `V=2` etc.). You can run as many follow-up visits as needed without approaching the limit.

**The limit counts cumulative enrollment across all waves.** If you enrol 10,000 in wave 1 and add 5,000 in wave 2, that is 15,000 total — leaving 15,000 remaining capacity at 5 digits.

**Plan your digit count before starting.** Digits cannot be changed after `init` — all IDs in a study must use the same count. Choose based on your maximum anticipated total enrollment, not your current sample size. For a study expecting 20,000 participants with possible extension, 5 digits is sufficient. If there is any chance of exceeding 30,000 over the study lifetime, use 6 digits from the start.

**Follow-up visit numbers can be any positive integer** (2, 3, 4 …). There is no upper limit.

Set `--digits` and `--visit` once in `init` and never change them.

---

## Scenario 1 — New study, generating IDs for incoming recruits

Use this when your study is starting fresh and you want to assign IDs to participants as they are recruited.

**Prepare a sample sheet** (`samples.xlsx` or `.csv` / `.txt`):

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA      | 50     | 100       |
| SiteB      | 30     | 60        |

Each row is a site (or sample group). `NCases` and `NControls` are the number of participants to register in this batch.

**Generate IDs:**

```bash
python3 idgenerator.py batch --input-file samples.xlsx --output ./ids
```

Output files are written to `./ids/`. The main files you will use are the master combined files in the top-level directory:

```
ids/
  YYYYMMDD_MyStudy_IDP_IDT_ALL_N=240.txt   ← personal data + temp keys, all sites
  YYYYMMDD_MyStudy_IDS_IDT_ALL_N=240.txt   ← study data + temp keys, all sites
  per_site/                                 ← individual files per site (for reference)
  LogFile.txt
  study.cfg
```

**Adding new recruits in a later wave:**

Update your sample sheet with the *additional* counts (not the total):

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA      | 20     | 40        |
| SiteC      | 15     | 30        |

```bash
python3 idgenerator.py batch --input-file wave2.xlsx --output ./ids
```

The script detects that SiteA already exists and extends it. SiteC is new and is created fresh. The master files are rebuilt to include all sites across all waves. Old per-site files are renamed `.old`.

---

## Scenario 2 — Multiple sites with different sample sizes

Use this when you have several contributing sites, each with their own case and control counts. This is the sheet-based workflow — prepare one input file per wave.

**Wave 1 input** (`wave1.txt` — create in any text editor or Excel, save as `.txt` or `.xlsx`):

```
SampleName    NCases    NControls
SiteA         200       400
SiteB         120       250
SiteC         80        160
```

```bash
python3 idgenerator.py batch --input-file wave1.txt --output ./ids
```

This generates IDs for all three sites in one run. The master files contain all sites combined; individual per-site files go to `ids/per_site/`.

**Wave 2 — extending some sites and adding a new one:**

```
SampleName    NCases    NControls
SiteA         30        60        ← 30 new cases added to SiteA's existing 200
SiteB         20        40        ← extended
SiteD         50        100       ← brand new site, created fresh automatically
```

```bash
python3 idgenerator.py batch --input-file wave2.txt --output ./ids
```

The counts in each wave are always **additional** subjects — not the running total. The script auto-detects which sites already exist and extends them; sites not seen before are created fresh. Every new ID is guaranteed unique across all previous waves.

After Wave 2 the master files are rebuilt to include all four sites (SiteA–D) across both waves.

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

Each output file has columns: `IDS | IDSV2 | IDS128 | IDSV2128` — the baseline and visit IDs side by side with their barcodes.

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
| Per-site `IDP_IDT_T=…` | `ids/per_site/` | Reference copy per site/group. |
| Per-site `IDS_IDT_T=…` | `ids/per_site/` | Reference copy per site/group. |
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
