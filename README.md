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

If your cohort collects multiple data types (genetics, phenotyping, imaging…), declare the tracks here too:

```bash
python3 idgenerator.py init \
    --study  MyStudy \
    --center 01 \
    --tracks Genetics,Phenotype \
    --output ./ids
```

Every subsequent `batch` call reads the track list from `study.cfg` automatically. Override `--tracks` on the command line at any time if a new data type is added later.

**Choosing `--blocks`** — each letter is a segment that is concatenated in order to form every ID:

| Letter | Segment | Example |
|--------|---------|---------|
| `C` | Center code (`--center`) | `01` |
| `T` | Track / sample name | `SiteA` |
| `G` | Group — case or control prefix | `S` or `C` |
| `N` | Unique random number | `12345` |
| `V` | Visit digit (IDP = `0`, baseline IDS = `1`) | `1` |
| `X` | Check digit (one character) | `7` |

With `--blocks CTGNVX`, center `01`, track `SiteA`, a case participant, N = `12345`, and check digit `7`:

```
01SiteAS1234517
```

`CTGNVX` is the right choice for multi-site studies with a case/control distinction. If your study has no case/control groups, drop `G` and use `CTNVX`. If all participants come from a single center you can drop `C` too.

> **Blinding caution:** embedding `G` in the ID exposes case/control status to anyone who sees it. Omit `G` if blinding is required.

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

## Scenario 1 — Single cohort, specifying counts directly

Use this when your study has one cohort and you want to assign IDs without creating an input file. Pass the sample size directly on the command line with `--samplesize`.

**No case/control distinction** (`--blocks CTNVX`, one number = total N):

```bash
python3 idgenerator.py batch \
    --samplesize 5000 \
    --blocks CTNVX \
    --output ./ids
```

**With cases and controls** (`--blocks CTGNVX`, two numbers = NCases NControls):

```bash
python3 idgenerator.py batch \
    --samplesize 50 80 \
    --blocks CTGNVX \
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

Use this when participants are already anonymised and you need separate, independent ID sets for different data types — genetics, phenotyping, imaging, and so on. Because there is no personal data to track, only IDS (study data IDs) are generated — no IDP. The IDT linkage key connects the data types across tracks; delete it once labelling is complete to fully sever that link.

Each data type is a **track**. Tracks are declared once at `init` and saved to `study.cfg`. The input sheet defines sites and participant counts; the tracks define what ID columns every participant at every site receives.

**Step 1 — save study parameters, declare tracks, mark as anonymised:**

```bash
python3 idgenerator.py init \
    --study    AnonymCohort \
    --center   01 \
    --blocks   CTGNVX \
    --tracks   Genetics,Phenotype \
    --anon \
    --output   ./ids
```

`--tracks` and `--anon` are stored in `study.cfg`. You do not need to repeat them on every `batch` call.

`--anon` is the key flag here: it tells the script to draw from the IDS pool and label output columns `IDS_Genetics`, `IDS_Phenotype` instead of IDP. Without it, the IDP (personal data) pool would be used.

**Step 2 — prepare the site sheet (`wave1.txt`):**

```
SampleName   NCases   NControls
SiteA        200      0
SiteB        150      75
```

Each row is a site. `NCases` is the participant count for that site. `NControls` can be used if a site has a case/control split; set it to `0` for sites with no distinction.

**Step 3 — generate IDs for Wave 1:**

```bash
python3 idgenerator.py batch \
    --input-file wave1.txt \
    --output ./ids \
    --seed 10
```

No `--tracks` flag needed — it is loaded from `study.cfg`. Every participant at every site receives one IDT and one IDS per track.

Output:

```
ids/
  YYYYMMDD_AnonymCohort_IDS_T=Genetics+Phenotype_ALL_N=350.txt   ← all sites combined
  per_site/
    YYYYMMDD_AnonymCohort_IDS_T=Genetics+Phenotype_SITE=SiteA_N=200_Baseline.txt
    YYYYMMDD_AnonymCohort_IDS_T=Genetics+Phenotype_SITE=SiteB_N=150_Baseline.txt
```

Per-site columns: `IDT | IDS_Genetics | IDS_Phenotype`  
Master ALL columns: `Site | IDT | IDS_Genetics | IDS_Phenotype`

**Adding participants in a later wave:**

Provide a new sheet with the *additional* counts for each site. The script detects existing per-site files and appends new rows — old files are renamed `.old` and the master ALL is rebuilt:

```bash
python3 idgenerator.py batch \
    --input-file wave2.txt \
    --output ./ids \
    --seed 11
```

**Tracks must be declared before the first batch run.** Every participant enrolled under a given track set receives IDS IDs for all of those tracks at enrolment. You cannot retroactively add a track to existing participants — doing so would require a new independent dataset with a different track tag, leaving prior participants without the new column. If you know you will eventually collect Genetics, Phenotype, and Imaging data, declare all three at `init` from the start.

**Starting a new parallel dataset with an additional track:**

Re-running `init` with a new track list and then running `batch` begins a fresh dataset for that track combination. Existing participants are not affected. The two datasets are independent and can be linked via IDT. Use this only for a genuinely new data collection effort (e.g. an imaging sub-study with its own enrolment list):

```bash
python3 idgenerator.py init \
    --study AnonymCohort --center 01 --blocks CTGNVX \
    --tracks Genetics,Phenotype,Imaging \
    --anon \
    --output ./ids

python3 idgenerator.py batch \
    --input-file wave3.txt \
    --output ./ids \
    --seed 12
```

**Single-site variant:**

For a cohort at one site, skip the sheet and pass the count directly. Note: the `baseline` command does not read `--anon` from config — it always generates IDP. Use `batch` with `--samplesize` for the anon path:

```bash
python3 idgenerator.py batch \
    --samplesize 500 \
    --output ./ids
```

Tracks and `--anon` are loaded from `study.cfg`. Output: `IDT | IDS_Genetics | IDS_Phenotype`.

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
