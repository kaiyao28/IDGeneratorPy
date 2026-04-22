# IDGeneratorPy

A command-line tool for generating and managing randomized participant IDs in clinical or epidemiological studies. It is a cross-platform Python port of [idGenerator](https://github.com/mpmky/idGenerator), originally written in VB.NET by the Genetic Epidemiology group at the University of Regensburg (Olden et al. 2016).

**Core workflow in three commands:**

```bash
python3 idgenerator.py init  --study MyStudy --center 01 --output ./ids  # once per project
python3 idgenerator.py batch --input-file samples.xlsx  --output ./ids   # generate IDs
python3 idgenerator.py followup                         --output ./ids   # follow-up visit IDs
```

Each participant receives three linked IDs — a personal ID (IDP), a study data ID (IDS), and a temporary linkage key (IDT) — drawn from separate random number pools. Deleting IDT severs the link between personal and study data, enabling full anonymisation.

> For a full explanation of the ID system, all command flags, checksum algorithms, and a detailed worked example, see [REFERENCE.md](REFERENCE.md).

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

**Choosing `--digits`** — the digit count determines the maximum number of participants your study can enrol. The available range is split equally across the three ID pools (IDP / IDS / IDT), so the limit per pool is roughly one third of the total range:

| `--digits` | Max participants |
|-----------|-----------------|
| `5` (default) | ~30,000 |
| `6` | ~300,000 |
| `7` | ~3,000,000 |

Set this once in `init` and never change it — all IDs in a study must use the same digit count.

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
| SiteA      | 20     | 40        |   ← 20 new cases, 40 new controls added to SiteA
| SiteC      | 15     | 30        |   ← SiteC is new — created fresh automatically

```bash
python3 idgenerator.py batch --input-file wave2.xlsx --output ./ids
```

The script detects that SiteA already exists and extends it. SiteC is new and is created fresh. The master files are rebuilt to include all sites across all waves. Old per-site files are renamed `.old`.

---

## Scenario 2 — Existing cohort, assigning IDs retrospectively

Use this when participants are already enrolled and you want to assign uniform IDs across the cohort for tracking and data linkage.

The workflow is identical to Scenario 1 — the difference is that your sample sheet lists the *current* cohort size rather than new recruits.

**Prepare a sample sheet** with current cohort sizes:

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA      | 200    | 400       |
| SiteB      | 120    | 250       |

**Generate IDs for the full existing cohort:**

```bash
python3 idgenerator.py batch --input-file cohort.xlsx --output ./ids
```

This produces one ID per row in the master files. Assign the IDs to existing participants.

**Adding new participants later:**

List only the *additional* subjects in the new sheet and run `batch` again — the same command as Scenario 1:

```bash
python3 idgenerator.py batch --input-file new_recruits.xlsx --output ./ids
```

Existing sites are extended automatically; new sites are created fresh.

---

## Follow-up visits

Once baseline IDs have been generated, a single command produces follow-up visit IDs for all sites. No input file is needed — the script reads the IDS files it already wrote to `ids/per_site/` automatically.

The visit number comes from `study.cfg` (the `--visit` value you set in `init`). The default is `2`.

```bash
python3 idgenerator.py followup --output ./ids
```

Output:

```
ids/
  YYYYMMDD_MyStudy_IDS_IDSV2_ALL_N=240_V=2.txt   ← all sites, baseline IDS → visit-2 IDS pairs
  followup/
    YYYYMMDD_MyStudy_IDS_IDSV2_T=SiteA_…_V=2.txt ← per-site files
```

To generate a different visit number without changing `study.cfg`:

```bash
python3 idgenerator.py followup --visit 3 --output ./ids
```

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
