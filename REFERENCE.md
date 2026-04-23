# IDGeneratorPy — Reference

This document covers all commands, flags, and the design of the ID system in detail. For the quick-start workflows see [README.md](README.md).

---

## How the ID system works

Each participant receives three linked IDs drawn from separate random number pools (Olden et al. 2016):

| ID | Pool (5-digit) | Purpose |
|----|----------------|---------|
| **IDP** (Personal data) | 10 000 – 39 999 | Links to name / address / date of birth. Restricted to study personnel. Visit digit is always `0`. |
| **IDS** (Study data) | 40 000 – 69 999 | Links to scientific data. Used by analysts. |
| **IDT** (Temporary) | 70 000 – 99 999 | Temporary linkage key between IDP and IDS. Appears in both files. Deleting it severs the link and makes the IDS file anonymous. |

The pool split ensures IDP and IDS numbers never collide and cannot be confused. Digit count is set by `--digits` (default: 5); the three pools always occupy the lower third, middle third, and upper third of the available range.

---

## Building blocks (`--blocks`)

IDs are assembled from a sequence of named building blocks:

| Block | Contents | When to include |
|-------|----------|-----------------|
| `C` | Recruiting site code (`--center`) | Multi-center studies |
| `T` | Track / sample name. In standard `batch` mode the full SampleName is used. In multi-track `batch --tracks` mode only the **first character** of each track name is embedded (e.g. `G` for Genetics, `P` for Phenotype) — column headers and filenames still use the full name. | Multiple sample types |
| `G` | Group prefix — case (`S`) or control (`C`) | `batch` mode with case/control distinction |
| `N` | Unique random number | Always |
| `V` | Visit number (IDP=0, IDS=1, follow-ups=n) | Longitudinal studies |
| `X` | Check digit (one character) | Recommended for all IDs |

Recommended block strings:

- `CTGNVX` — batch mode with cases and controls
- `CTNVX` — single-track or no case/control distinction

> **Re-identification caution:** Embedding group membership (`G`) in the ID exposes case/control status to anyone who knows the encoding. Omit `G` if blinding is required.

Example ID with `CTGNVX`, center `01`, track `Sample001`, group `S`, N=`12345`, visit `1`:
```
01Sample001S123451X
```
where `X` is the computed check digit.

---

## Checksum algorithms (`--checksum`)

| Name | Description |
|------|-------------|
| `none` | No check digit |
| `Simple_Parity` | Sum of character values mod 10 |
| `Weighted_Parity` | Sum of (character value × position) mod 10 |
| `Gumm_1986` | Gumm (1986) algorithm |
| `Damm_2004` | Damm (2004) algorithm — **default, recommended** |

---

## Commands

All commands (except `init`) automatically load settings from `study.cfg` if it exists in the output directory. CLI flags always override saved values.

---

### `init` — save study parameters

Run once per project. Writes `study.cfg` to `--output`.

```bash
python3 idgenerator.py init \
    --study           MyStudy \
    --center          01 \
    --digits          5 \
    --blocks          CTGNVX \
    --checksum        Damm_2004 \
    --case-prefix     S \
    --control-prefix  C \
    --visit           2 \
    --output          ./ids
```

| Parameter | Default | Saved to `study.cfg` |
|-----------|---------|----------------------|
| `--study` | *(required)* | yes |
| `--center` | `""` | yes |
| `--digits` | `5` | yes |
| `--blocks` | `CTNVX` | yes |
| `--checksum` | `Damm_2004` | yes |
| `--case-prefix` | `S` | yes |
| `--control-prefix` | `C` | yes |
| `--visit` | `2` | yes |
| `--tracks` | *(none)* | yes — auto-loaded by `batch` for multi-track mode |
| `--anon` | `false` | yes — switches multi-track `batch` from IDP pool to IDS pool |
| `--output` | `.` | yes |

---

### `batch` — generate IDs from inline counts or a sample sheet

The main command. Generates one IDP and one IDS file per site × group. Accepts either inline counts on the command line or a sample sheet file.

**Inline mode** — no input file needed:

```bash
# Single group (no case/control distinction, --blocks without G):
python3 idgenerator.py batch \
    --samplesize 5000 \
    --output ./ids

# Case/control groups (--blocks with G):
python3 idgenerator.py batch \
    --samplesize 50 80 \
    --output ./ids
```

`--samplesize` takes one value when `G` is absent from `--blocks`, two values (NCases NControls) when `G` is present. The track name defaults to the study name; override with `--track MyCohort`.

**Sheet mode** — specify counts in a file:

```bash
python3 idgenerator.py batch \
    --input-file  samples.xlsx \
    --output      ./ids
```

**Input file columns** (`.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt`):

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA | 50 | 100 |
| SiteB | 30 | 60 |

Column names are flexible (case-insensitive). Accepted aliases:
- Sample: `SampleName`, `Sample`, `sample_name`, `Name`, `ID`
- Cases: `NCases`, `Cases`, `N_Cases`, `NCase`
- Controls: `NControls`, `Controls`, `N_Controls`, `NControl`, `Ctrl`

**Optional flags:**

| Flag | Effect |
|------|--------|
| `--samplesize <N>` or `<N M>` | Inline counts — alternative to `--input-file`. |
| `--track <name>` | Track/cohort name when using `--samplesize` (default: study name). |
| `--tracks <T1,T2,...>` | Multi-track mode: comma-separated data track names. The sheet defines sites and counts; `--tracks` defines what IDS columns each participant receives. Auto-loaded from `study.cfg` if set at `init`. |
| `--fresh` | Treat every row as new — do not extend any existing baseline. |
| `--shuffle` | Randomise row order in per-site IDS files. Breaks positional re-identification if the file is extracted from its context. Unshuffled by default. |
| `--seed <int>` | Fix the random seed for reproducible output. Recorded in `LogFile.txt`. |
| `--input-dir <path>` | Look for existing baselines here instead of `--output`. |

**Auto-extend behaviour (default):**

For each site + group, `batch` checks whether a baseline already exists:
- If found → extend (preserve existing IDs, append new ones, rename old file to `.old`)
- If not found → create fresh

The counts are always **additional** subjects. Use `--fresh` to override this and force all rows to be created new.

**Output layout:**

```
ids/
  YYYYMMDD_{study}_IDP_IDT_ALL_N={total}.txt     ← master: all sites/groups, personal data
  YYYYMMDD_{study}_IDS_IDT_ALL_N={total}.txt     ← master: all sites/groups, study data
  LogFile.txt
  study.cfg
  per_site/
    YYYYMMDD_{study}_IDP_IDT_T={s}_G=S_N={n}_Baseline.txt   ← first creation
    YYYYMMDD_{study}_IDP_IDT_T={s}_G=S_N={n}_Extended.txt   ← after extending
    YYYYMMDD_{study}_IDS_IDT_T={s}_G=S_N={n}_Baseline.txt
    *.old                                                     ← superseded files
```

The master ALL files are rebuilt after every run, so they always contain all sites across all waves.

---

### `baseline` — generate a fresh baseline for named tracks

Two modes depending on whether `--samplesize` is provided:

**Multi-track mode** (`--samplesize N --tracks Name1,Name2,...`)

Every participant receives one IDT and one IDP per track. All tracks share the same N — if a participant is missing data for one track they still hold an ID for it. Output is one file with track IDs as columns.

```bash
python3 idgenerator.py baseline \
    --samplesize 500 \
    --tracks     Genetics,Phenotype,Imaging \
    --output     ./ids
```

Output file: `YYYYMMDD_{study}_IDP_T=Genetics+Phenotype+Imaging_N=500_Baseline.txt`  
Columns: `IDT | IDP_Genetics | IDP_Phenotype | IDP_Imaging`

**Single-track mode** (`--tracks "Name:count,..."`, no `--samplesize`)

Generates one IDP/IDS file pair per track, each with its own count. Use when tracks genuinely have different sizes.

```bash
python3 idgenerator.py baseline \
    --tracks  "TrackA:100,TrackB:200" \
    --output  ./ids
```

Optional: `--shuffle`, `--seed`

---

### `followup` — generate follow-up visit IDs

Reads all current IDS_IDT files from `per_site/` (both `_Baseline` and `_Extended`) and produces IDS↔IDSVn pairs. Visit number is read from `study.cfg`; override with `--visit`.

```bash
python3 idgenerator.py followup --output ./ids

# Override visit number for this run only:
python3 idgenerator.py followup --visit 3 --output ./ids
```

Output:

```
ids/
  YYYYMMDD_{study}_IDS_IDSV{n}_ALL_N={total}_V={n}.txt
  followup/
    YYYYMMDD_{study}_IDS_IDSV{n}_T={s}_G={g}_N={n}_V={n}.txt
```

Columns per-site: `IDS | IDSVn | IDS128 | IDSVn128`  
Columns ALL: `IDS | IDSVn | Track | Group`

---

### `extend` — add subjects to an existing baseline

Two modes mirroring `baseline`:

**Multi-track mode** (omit `--tracks` — tracks auto-detected from the existing file)

```bash
python3 idgenerator.py extend \
    --new-samples 100 \
    --input-dir   ./ids \
    --output      ./ids
```

`--new-samples` is the number of new participants to add. All tracks in the existing file are extended by the same count simultaneously.

**Single-track mode** (provide `--tracks` with current counts)

```bash
python3 idgenerator.py extend \
    --tracks       "TrackA:100,TrackB:200" \
    --new-samples  "TrackA:20,TrackB:30" \
    --input-dir    ./ids \
    --output       ./ids
```

`--tracks` is the *current* count per track; `--new-samples` is what to add per track.

In both modes old files are renamed `.old`.

---

### `add-track` — create an empty baseline placeholder

Creates a header-only (`N=0`) file for a new track, ready to be extended later.

```bash
python3 idgenerator.py add-track \
    --study   MyStudy \
    --track   TrackC \
    --output  ./ids
```

---

### `external` — create external-project IDs

Creates IDE IDs (one digit wider than study IDs) linked to existing IDS records via IDT.

```bash
python3 idgenerator.py external \
    --ext-project  ExtProj \
    --input-dir    ./ids \
    --output       ./ids
```

Output columns: `IDS | IDE | IDS128 | IDE128`

---

## Output file reference

All output files are **tab-separated `.txt`** with a single header row. `*128` columns contain Code 128 barcode-encoded strings.

| File type | Columns |
|-----------|---------|
| `IDP_IDT` per-site | `IDP`, `IDP128`, `IDT` |
| `IDS_IDT` per-site | `IDS`, `IDS128`, `IDT` |
| `IDP_IDT` ALL master | `IDP`, `IDT`, `Track`, `Group` |
| `IDS_IDT` ALL master | `IDS`, `IDT`, `Track`, `Group` |
| Follow-up per-site | `IDS`, `IDSVn`, `IDS128`, `IDSVn128` |
| Follow-up ALL | `IDS`, `IDSVn`, `Track`, `Group` |
| External | `IDS`, `IDE`, `IDS128`, `IDE128` |

> **Why no barcodes in ALL master files?** Code 128 barcode strings occasionally contain a space character (when the check value equals 0), which breaks Excel VLOOKUP and R `merge()` / `trimws()`. Per-site files keep barcodes for tube label printing; the master analytical files contain only plain IDs.

**Filename conventions:**

- `_Baseline` — first time a site/group was generated
- `_Extended` — file was extended with additional subjects
- `_ALL_` in name — master file combining all sites (no status suffix)
- `.old` extension — superseded by a newer version

---

## Test sets

Three self-contained test directories are provided, one per scenario. Each can be run independently from the `idGenerator_python/` directory.

| Directory | Scenario | Key commands |
|-----------|----------|--------------|
| `test_scenario1/` | Single cohort, inline counts, case/control, follow-up | `batch --samplesize`, `followup` |
| `test_scenario2/` | Multi-track anonymised cohort, sheet input, `--anon` | `init --tracks --anon`, `batch --input-file` |
| `test_full/` | Multi-site, multi-wave with sheet input | `batch --input-file`, `followup` |

Each directory contains a `commands.sh` with the exact commands to run in order.

```bash
bash test_scenario1/commands.sh
bash test_scenario2/commands.sh
```

---

## Detailed worked example

This example covers all major commands with multiple waves, an extension, a shuffle run, and a follow-up. Input files are in `test_full/`.

### Input files

The input files are in `test_full/`:

**wave1.txt** (Wave 1 — three new sites):
```
SampleName	NCases	NControls
SiteA	20	40
SiteB	15	30
SiteC	10	20
```
Total N = 135

**wave2.txt** (Wave 2 — extend SiteA, add new SiteD):
```
SampleName	NCases	NControls
SiteA	5	10
SiteD	8	16
```
Adds 39; running total N = 174

**wave3.txt** (Wave 3 — add new SiteE, shuffled):
```
SampleName	NCases	NControls
SiteE	6	12
```
Adds 18; running total N = 192

### Run all steps

```bash
# Step 1 — save study parameters
python3 idgenerator.py init \
    --study TestStudy --center 01 \
    --digits 5 --blocks CTGNVX --checksum Damm_2004 \
    --case-prefix S --control-prefix C --visit 2 \
    --output test_full/ids

# Step 2 — Wave 1: all six site×group combinations are new
python3 idgenerator.py batch \
    --input-file test_full/wave1.txt \
    --output test_full/ids \
    --seed 42

# Step 3 — Wave 2: SiteA is extended; SiteD is new (auto-detected)
python3 idgenerator.py batch \
    --input-file test_full/wave2.txt \
    --output test_full/ids \
    --seed 43

# Step 4 — Wave 3: SiteE is new; --shuffle randomises row order in IDS files
python3 idgenerator.py batch \
    --input-file test_full/wave3.txt \
    --output test_full/ids \
    --shuffle --seed 44

# Step 5 — Follow-up visit 2 for all sites (visit number from study.cfg)
python3 idgenerator.py followup \
    --output test_full/ids
```

### What to expect after each step

**After Step 2 (Wave 1):**
```
test_full/ids/
  20XXXXXX_TestStudy_IDP_IDT_ALL_N=135.txt
  20XXXXXX_TestStudy_IDS_IDT_ALL_N=135.txt
  per_site/
    20XXXXXX_TestStudy_IDP_IDT_T=SiteA_G=S_N=20_Baseline.txt
    20XXXXXX_TestStudy_IDP_IDT_T=SiteA_G=C_N=40_Baseline.txt
    20XXXXXX_TestStudy_IDP_IDT_T=SiteB_G=S_N=15_Baseline.txt
    20XXXXXX_TestStudy_IDP_IDT_T=SiteB_G=C_N=30_Baseline.txt
    20XXXXXX_TestStudy_IDP_IDT_T=SiteC_G=S_N=10_Baseline.txt
    20XXXXXX_TestStudy_IDP_IDT_T=SiteC_G=C_N=20_Baseline.txt
    (+ matching IDS_IDT files)
```

**After Step 3 (Wave 2):**
- SiteA `_Baseline.txt` renamed to `.old`; new `_Extended.txt` written (25S / 50C)
- SiteD files created fresh as `_Baseline.txt`
- Master ALL rebuilt: all five sites (A–D), N=174 total

**After Step 4 (Wave 3):**
- SiteE files created as `_Baseline.txt`
- `--shuffle` randomises row order in per-site IDS files for SiteE
- Master ALL rebuilt: all six sites (A–E), N=192 total

**After Step 5 (Follow-up):**
```
test_full/ids/
  20XXXXXX_TestStudy_IDS_IDSV2_ALL_N=192_V=2.txt    ← IDS | IDSV2 | Track | Group
  followup/
    20XXXXXX_TestStudy_IDS_IDSV2_T=SiteA_G=S_N=25_V=2.txt
    20XXXXXX_TestStudy_IDS_IDSV2_T=SiteA_G=C_N=50_V=2.txt
    … (one file per site/group, including SiteE)
```

All six sites appear in the follow-up master, including SiteE whose IDS file was shuffled.

### Key observations

- **`--seed`** makes runs reproducible. The seed is recorded in `LogFile.txt`.
- **Wave auto-detection**: the script reads the per-site files in `per_site/` to determine what already exists. Do not delete or rename those files between waves.
- **Unique IDs across all waves**: existing numbers are read back from old files before new numbers are drawn, so there is no risk of collision.
- **`_Baseline` vs `_Extended`**: a site that has been extended will always have `_Extended.txt` as its current per-site file. The `_Baseline.txt` for that site is retained as `.old` for audit purposes.
- **Master files**: after every `batch` run the master `_ALL_` files are rebuilt from scratch from all current per-site files, so they represent the complete state of the study at that moment.

---

## Credits

> Olden M, Holle R, Heid IM, Stark K.  
> *IDGenerator: unique identifier generator for epidemiologic or clinical studies.*  
> BMC Medical Research Methodology. 2016;16(1):103.  
> DOI: [10.1186/s12874-016-0222-3](https://doi.org/10.1186/s12874-016-0222-3)

Source: [osf.io/urs2g](https://osf.io/urs2g/) — Genetic Epidemiology, University of Regensburg.
