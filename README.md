# IDGeneratorPy

Cross-platform Python port of [idGenerator](https://github.com/mpmky/idGenerator) (Olden et al. 2016, University of Regensburg). Generates three linked but independent IDs for each participant:

- **IDP** (Personal) — ties to identifying information such as name, date of birth, and contact details. Held only by study personnel.
- **IDS** (Study) — ties to scientific data (measurements, samples, questionnaires). Shared with analysts. Contains no personal information.
- **IDT** (Temporary linkage key) — the only bridge between IDP and IDS. Deleting it permanently severs the link, making the IDS file fully anonymous while keeping the scientific dataset intact.

All three are drawn from separate random number pools so they can never be confused with one another.

> Full command reference, flag descriptions, and a multi-wave worked example: [REFERENCE.md](REFERENCE.md)  
> Changes and new features relative to the original VB.NET programme: [CHANGES.md](CHANGES.md)

---

## Requirements

- Python 3.7+
- `.txt` / `.csv` input: no dependencies
- Excel input (`.xlsx` / `.xls`): `pip install openpyxl`

---

## Setup — save study parameters once

```bash
git clone https://github.com/kaiyao28/IDGeneratorPy.git
cd IDGeneratorPy

python3 idgenerator.py init \
    --study    MyStudy \
    --center   01 \
    --blocks   CRGNVX \
    --checksum Damm_2004 \
    --output   ./ids
```

`init` writes `study.cfg`; every subsequent command loads it automatically. Set `--blocks`, `--digits`, `--checksum` here — not on every batch call.

**Multi-center:** give each center its own output folder with a different `--center` code. New centers can be added at any time. See [REFERENCE.md](REFERENCE.md) for details.

### Choosing `--blocks`

`--blocks` is a string of letters that defines what appears in every ID, in order. The only required letter is `N` — the unique random number. Everything else is an optional label you wrap around it so the ID is self-describing at a glance.

Standard batch — `--blocks SCRGNVX` with `--study MyStudy --center 01`, case participant at SiteA:

```
MyStudy · 01     · SiteA · S     · 12345  · 1  · 7
   S        C        R       G       N       V    X
 study   center   site    group   random  type check
                          (case)  number
```

Multi-track batch — `--blocks SCRTNVX`, site SiteA, track Genetics:

```
MyStudy · 01     · SiteA · G     · 12345  · 1  · 7
   S        C        R       T       N       V    X
 study   center   site    track   random  type check
                         (abbrev) number
```

Each letter maps to one segment:

| Letter | What it adds | Notes |
|--------|-------------|-------|
| `S` | Study name (`--study`) | Embeds your study name as a prefix in every ID |
| `C` | Center code (`--center`) | Any string — numbers (`01`) or letters (`LON`) both work. Include for multi-center studies |
| `R` | Recruitment site name | `SampleName` from the input sheet |
| `T` | Data-track abbreviation | First character of each `--tracks` name (`G`=Genetics, `P`=Phenotype). **Requires `--tracks` declared at `init`** — omit if no tracks; all participants then receive a single uniform IDS |
| `G` | Case/control prefix | Default `S` cases, `C` controls — change with `--case-prefix` / `--control-prefix`. Works in all modes including multi-track. Omit if no case/control distinction needed |
| `N` | Unique random number | **Required** |
| `V` | ID-type flag | `0` = IDP (personal), `1` = IDS or IDT. Not a visit counter. Omit if you don't need to tell IDP from IDS at a glance |
| `X` | Check digit | Computed from the rest of the ID — catches transcription errors on tube labels. Safe to omit for digital-only workflows |

Common starting points:

| `--blocks` | Mode | Example ID | When to use |
|------------|------|-----------|------------|
| `CRGNVX` | Standard | `01SiteAS123451X` | Multi-site case/control |
| `CRNVX` | Standard | `01SiteA123451X` | No case/control distinction |
| `CRTNVX` | Multi-track | `01SiteAG123451X` | Site + track both visible |
| `SCN` | Anonymised | `MyStudy0112345` | Minimal — Scenario 2 |

### Choosing `--digits`

`--digits` controls how many digits `N` uses (default `5`), which sets your maximum total enrolment across all recruitment waves:

| `--digits` | Max participants |
|-----------|----------------|
| `5` (default) | ~30,000 |
| `6` | ~300,000 |
| `7` | ~3,000,000 |

Set this once at `init` — it cannot be changed after IDs have been generated. If you need more capacity, start a fresh study in a new output folder with a higher digit count. Follow-up visits do not count toward the limit. See [REFERENCE.md](REFERENCE.md) for full details.

---

## Scenario 1 — Assign IDs by count

Use this when you are recruiting participants into a new study and want to assign IDP + IDS + IDT as people enrol. IDs are generated in batches; later waves extend the existing records automatically — no ID is ever reused. Deleting the IDT column at any point fully severs the link between personal and study data.

Run `init` first (see above), then:

```bash
# All participants in one group (no site label — study name used as site)
python3 idgenerator.py batch --samplesize 5000 --output ./ids

# Cases and controls at a named site — R in --blocks embeds the site name in every ID
python3 idgenerator.py batch --samplesize 50 80 --site SiteA --output ./ids
```

**Extend in a later wave** — pass the *additional* count; existing records are preserved automatically:

```bash
# Manual: --site SiteA finds the existing file and appends
python3 idgenerator.py batch --samplesize 10 20 --site SiteA --output ./ids
```

Manual (`--site`) and sheet input can be freely mixed across waves. The site name is the link — `--site SiteA` manually matches `SampleName SiteA` in a sheet:

```bash
# Wave 1 — manual
python3 idgenerator.py batch --samplesize 50 80 --site SiteA --output ./ids --seed 1

# Wave 2 — sheet (SampleName column must match the --site value used above)
python3 idgenerator.py batch --input-file wave2.txt --output ./ids --seed 2
```

```
# wave2.txt
SampleName  NCases  NControls
SiteA       10      20
```

---

## Scenario 2 — Assign IDS keys to an anonymised cohort

Use this when participants are already anonymous but have inconsistent or site-specific identifiers, and you need a single uniform key for data linkage. Only IDS is generated — no personal IDP. The IDT links records across data types; delete it once labelling is complete. `--anon` switches the script to this mode.

```bash
python3 idgenerator.py init \
    --study  AnonymCohort \
    --center 01 \
    --blocks SCN \
    --anon \
    --output ./ids
```

`--blocks SCN` is the minimal setting for an anonymised cohort: study prefix + center + random number. No track in the ID (tracks are separate columns), no visit digit (follow-ups use a `V2_` prefix), no checksum. Add `X` if IDs will be printed on tube labels.

Prepare a site sheet — `.txt` or `.csv` recommended (no dependencies). Excel `.xlsx` also accepted but requires `pip install openpyxl`.

```
SampleName   NCases   NControls
SiteA        200      0
SiteB        150      75
```

Generate IDs:

```bash
# txt or csv — no extra dependencies
python3 idgenerator.py batch --input-file wave1.csv --output ./ids --seed 10

# Excel — requires openpyxl
python3 idgenerator.py batch --input-file wave1.xlsx --output ./ids --seed 10
```

**Extend** with a new sheet of *additional* counts:

```bash
python3 idgenerator.py batch --input-file wave2.txt --output ./ids --seed 11
```

**Tracks** — if different data types (genetics, phenotyping…) need separate independent ID sets, declare them at `init` with `--tracks Genetics,Phenotype`. Each participant then gets `IDS_Genetics` and `IDS_Phenotype` columns. Tracks must be declared before the first batch run.

```bash
# Declare at init — T must be in --blocks to embed the track abbreviation in each ID
python3 idgenerator.py init --blocks CRTNVX --tracks Genetics,Phenotype --output ./ids

# Create an empty placeholder for a new track, ready to extend later
python3 idgenerator.py add-track --track Imaging --output ./ids
```

---

## Follow-up visits

```bash
python3 idgenerator.py followup --output ./ids          # visit number from study.cfg
python3 idgenerator.py followup --visit 3 --output ./ids
```

Each follow-up ID is the baseline IDS prefixed with the visit tag (`V2_…`, `V3_…`). No new random numbers are drawn.

---

## Credits

> Olden M, Holle R, Heid IM, Stark K. *IDGenerator: unique identifier generator for epidemiologic or clinical studies.* BMC Medical Research Methodology. 2016;16(1):103. DOI: [10.1186/s12874-016-0222-3](https://doi.org/10.1186/s12874-016-0222-3)

Source: [osf.io/urs2g](https://osf.io/urs2g/) — Genetic Epidemiology, University of Regensburg. Python adaptation: kaiyao28
