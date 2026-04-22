# IDGeneratorPy

A cross-platform Python adaptation of [idGenerator](https://github.com/mpmky/idGenerator) — a randomized clinical study ID generator originally written in VB.NET / Windows Forms by the Genetic Epidemiology group at the University of Regensburg (2016).

The original programme runs on Windows only. This port re-implements the same generation logic, checksum algorithms, and output file formats as a plain Python 3 command-line script that runs on Windows, macOS, and Linux with no dependencies beyond the standard library.

---

## How it works

Each subject receives three linked IDs generated from separate random pools:

| ID | Pool range (5-digit example) | Purpose |
|----|------------------------------|---------|
| **IDP** (Personal data) | 10 000 – 39 999 | Links to personally identifiable information (name, address, date of birth). Restricted to recruiting and study personnel only. Visit digit is always `0`. |
| **IDS** (Study data) | 40 000 – 69 999 | Links to scientific study data. Used by study analysts. Row order is randomised in the IDS_IDT file to prevent re-association by file position. |
| **IDT** (Temporary) | 70 000 – 99 999 | Temporary linkage key between IDP and IDS. Appears in both files. Can be deleted after the study for full anonymisation of the IDS file. |

> **Note on IDT:** Because ID-T is the only link between personal and study data, deleting the ID-T column (and the mapping table) from the IDS file is sufficient to render it anonymous. This is a core feature of the design per Olden et al. 2016.

IDs are assembled from configurable **building blocks** (`--blocks`):

| Block | Meaning | When to use |
|-------|---------|-------------|
| `C` | **Study center** — the recruiting site (hospital, clinic, or lab). Embed this when your study runs across multiple sites so you can tell from the ID alone where a participant was enrolled. E.g. `01` = site 1, `02` = site 2. | Multi-center studies |
| `T` | **Track** — the sample type or sub-study pipeline (e.g. `Blood`, `Urine`, `DNA`). Each track gets its own file pair. Embed this when one participant contributes more than one sample type so IDs from different lab pipelines cannot be mixed up. In `batch` mode, the `SampleName` column in your sheet fills this block. | Studies with multiple sample types |
| `G` | **Group** — case/control label (e.g. `S` for cases, `C` for controls). Used with the `batch` command only. | Case/control batch runs |
| `N` | **Unique random number** — the core random identifier drawn from a pool specific to the ID type (IDP / IDS / IDT). | Always required |
| `V` | **Visit number** — `0` for IDP (personal data), `1` for IDS/IDT at baseline, higher integers for follow-up visits. | Longitudinal studies |
| `X` | **Check digit** — a single computed digit appended to detect transcription errors. | Recommended for all IDs |

> **Re-identification caution (per Olden et al. 2016):** Embedding participant characteristics (such as case/control status via `G`, or a sample type via `T`) directly in the ID should be done with care. If the code mapping is known, the ID itself can reveal group membership and potentially undermine blinding. Only embed characteristics that are not sensitive in your study design.

Example with `--blocks CTGNVX`, center `01`, sample `Sample001`, group `S`, N=`12345`, visit `1`, check digit `4`:

```
01Sample001S123451 4
↑C  ↑T         ↑G ↑N    ↑V↑X
```

---

## Requirements

- Python 3.7 or later
- No third-party packages required for `.txt` / `.csv` / `.tsv` input
- For Excel input (`.xlsx`): `pip install openpyxl`
- For legacy Excel input (`.xls`): `pip install xlrd`

---

## Installation

```bash
git clone https://github.com/kaiyao28/IDGeneratorPy.git
cd IDGeneratorPy
python idgenerator.py --help
```

---

## Typical workflow: one coordinating center, samples from multiple contributing sites

A common scenario is a **single coordinating lab** that assigns IDs for samples arriving from several contributing sites (hospitals, clinics, etc.) over time. New samples can arrive from sites that have already been registered, or from entirely new sites.

In this setup:
- `--study` and `--center` are fixed for the life of the project — they identify your lab and study
- The `SampleName` column in the sheet is the **contributing site name** (not your own center)
- Cases and controls are tracked separately per site via the `G` block

> Note: the `C` building block encodes *your* coordinating center code and stays the same for every ID. The contributing site name goes into the `T` (track) block via `SampleName`.

---

### One-time setup — save study parameters

Run `init` once at the start of the project. It writes a `study.cfg` file that every subsequent command will load automatically, so you never have to repeat `--study`, `--center`, `--digits`, etc.

```bash
python idgenerator.py init \
    --study MyStudy --center 01 \
    --digits 5 --blocks CTGNVX --checksum Damm_2004 \
    --case-prefix S --control-prefix C --visit 2 \
    --output ./ids
```

---

### Wave 1 — first batch of samples arrives

`wave1.xlsx` (or `.csv` / `.txt`):

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA      | 50     | 100       |
| SiteB      | 30     | 60        |

```bash
python idgenerator.py batch --input-file wave1.xlsx --output ./ids
```

All study parameters are loaded automatically from `./ids/study.cfg`. A single combined file is produced:

```
{ts}_MyStudy_IDP_IDT_ALL_N=180_Baseline.txt    ← all sites, personal data + temp keys
```

Two combined files are always written to the main directory: `IDP_IDT_ALL` (personal data) and `IDS_IDT_ALL` (study data). Individual per-site files are always written to `per_site/`. Add `--shuffle` to also write per-site IDS files (with shuffled row order) into `per_site/`.

---

### Wave 2 — more samples from existing sites, plus a brand-new site

`wave2.xlsx`:

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA      | 20     | 40        |
| SiteC      | 15     | 30        |

- **SiteA** already has a baseline → will be **extended** automatically (new IDs appended; old files renamed `.old`)
- **SiteC** is new → will be **created fresh** automatically

```bash
python idgenerator.py batch --input-file wave2.xlsx --output ./ids
```

The script checks `./ids/` for each site's existing baseline and auto-detects extend vs new — no `--extend` flag needed. To force all rows to be treated as new regardless, use `--fresh`. Every new random number is guaranteed unique across all previous waves.

---

### What each output file is for

By default each `batch` run produces **one combined file** containing all sites and groups, with `Track` and `Group` columns added so the source is immediately readable. Pass `--separate` to also write individual per-site/group files alongside the combined one.

| File | Location | Who uses it | Contains |
|------|----------|-------------|----------|
| `IDP_IDT_ALL` | `output/` | Your team (coordinating center) | All personal data identifiers + temporary keys for this run, with Track and Group columns. Keep confidential. **Always written.** |
| `IDS_IDT_ALL` | `output/` | Lab / analysts | All study data identifiers + temporary keys, with Track and Group columns. **Always written.** |
| `IDP_IDT_T=…` | `output/per_site/` | Your team | Per-site/group IDP file. Always written here; `.old` archive kept when a site is extended. |
| `IDS_IDT_T=…` | `output/per_site/` | Lab / analysts | Per-site IDS file with shuffled row order. Written only with `--shuffle`. |

Once data collection is complete and linkage is no longer needed, the IDT column can be deleted from the IDS file to make it fully anonymous.

### Reproducible generation with `--seed`

Pass `--seed <integer>` to any command to fix the random number generator. Running the same command twice with the same seed produces identical IDs — useful for validation or re-generating lost output.

```bash
python idgenerator.py batch ... --seed 42
```

The seed is recorded in `LogFile.txt` alongside the full argument list.

---

### A complete multi-wave example

The `test_full/` directory in this repository contains ready-to-run input sheets and the expected output for every major command. It is the quickest way to verify that your installation is working.

**Input sheets included:**

| File | Contents |
|------|----------|
| `test_full/samples.csv` | Wave 1 — SiteA (10 cases, 20 controls) and SiteB (5 cases, 10 controls) |
| `test_full/wave2.csv` | Wave 2 — extend SiteA (+3/+5) and add SiteC fresh (4 cases, 8 controls) |
| `test_full/wave3.csv` | Wave 3 — SiteD (5 cases, 5 controls) with `--shuffle` to produce IDS files |

**Run all steps in order:**

```bash
# Once only — save study parameters to study.cfg (including follow-up visit number)
python idgenerator.py init \
    --study TestStudy --center 01 \
    --digits 5 --blocks CTGNVX --checksum Damm_2004 \
    --case-prefix S --control-prefix C --visit 2 \
    --output test_full/ids

# Wave 1 — all parameters loaded from study.cfg
python idgenerator.py batch --input-file test_full/samples.csv --seed 42 --output test_full/ids

# Wave 2 — auto-detects SiteA exists → extends; SiteC is new → creates
python idgenerator.py batch --input-file test_full/wave2.csv --seed 43 --output test_full/ids

# Wave 3 — new site; --shuffle randomises row order in per-site IDS file
python idgenerator.py batch --input-file test_full/wave3.csv --shuffle --seed 44 --output test_full/ids

# Follow-up — visit number loaded from study.cfg; covers all sites in one command
python idgenerator.py followup --output test_full/ids
```

After each wave, the master `IDP_IDT_ALL` and `IDS_IDT_ALL` files are rebuilt from every current per-site file, so they always contain all sites across all waves. The `followup` command likewise produces a master `IDS_IDSV2_ALL` covering all sites. After running, `test_full/ids/LogFile.txt` contains a full timestamped audit trail.

---

## Commands

### `init` — save study parameters once

Run once per project to write `study.cfg` to the output directory. All subsequent commands load it automatically, so you only need `--output` (and any per-run flags like `--input-file` or `--seed`).

```bash
python idgenerator.py init \
    --study MyStudy \
    --center 01 \
    --digits 5 \
    --blocks CTGNVX \
    --checksum Damm_2004 \
    --case-prefix S \
    --control-prefix C \
    --visit 2 \
    --output ./output
```

| Parameter | Saved | Default |
|-----------|-------|---------|
| `--study` | yes | *(required)* |
| `--center` | yes | `""` |
| `--digits` | yes | `5` |
| `--blocks` | yes | `CTNVX` |
| `--checksum` | yes | `Damm_2004` |
| `--case-prefix` | yes | `S` |
| `--control-prefix` | yes | `C` |
| `--visit` | yes | `2` |
| `--output` | yes | `.` |

CLI flags always take precedence over `study.cfg` values, which in turn take precedence over built-in defaults.

---

### `baseline` — generate a fresh baseline from named tracks

```bash
python idgenerator.py baseline \
    --study  MyStudy \
    --center 01 \
    --tracks "TrackA:100,TrackB:200" \
    --digits 5 \
    --blocks CTNVX \
    --checksum Damm_2004 \
    --output ./output
```

`--tracks` format: `"Name1:count1,Name2:count2,..."`

---

### `batch` — generate a baseline from a sample sheet (cases + controls)

This is the recommended command when you have a list of samples, each with a number of cases and controls.

```bash
python idgenerator.py batch \
    --study      MyStudy \
    --center     01 \
    --input-file samples.xlsx \
    --digits     5 \
    --blocks     CTGNVX \
    --checksum   Damm_2004 \
    --case-prefix    S \
    --control-prefix C \
    --output ./output
```

**Input file** (`.xlsx`, `.xls`, `.csv`, `.tsv`, or `.txt`):

| SampleName | NCases | NControls |
|------------|--------|-----------|
| Sample001  | 100    | 200       |
| Sample002  | 50     | 75        |

Column names are flexible (case-insensitive). Accepted aliases:

- Sample name: `SampleName`, `Sample`, `sample_name`, `Name`, `ID`
- Cases: `NCases`, `Cases`, `N_Cases`, `NCase`
- Controls: `NControls`, `Controls`, `N_Controls`, `NControl`, `Ctrl`

The `G` block in `--blocks CTGNVX` embeds the case/control prefix directly in every ID, making the group membership visible at a glance and consistent across all samples:

```
01Sample001S123451 4   ← case   (G = S)
01Sample001C456782 7   ← control (G = C)
```

Random numbers are drawn from a **global pool** across all samples and groups, so every ID in the entire run is guaranteed unique.

**Output structure:**
```
output/
  {ts}_{study}_IDP_IDT_ALL_N={total}_Baseline.txt   ← all sites/groups merged (always)
  {ts}_{study}_IDS_IDT_ALL_N={total}_Baseline.txt   ← all study IDs merged   (always)
  per_site/
    {ts}_{study}_IDP_IDT_T={s}_G=S_N={n}_Baseline.txt   ← per-site IDP (always)
    {ts}_{study}_IDP_IDT_T={s}_G=C_N={n}_Baseline.txt
    {ts}_{study}_IDS_IDT_T={s}_G=S_N={n}_Baseline.txt   ← per-site IDS (with --shuffle only)
    {ts}_{study}_IDS_IDT_T={s}_G=C_N={n}_Baseline.txt
```

---

#### Auto-detect extend vs new (default behaviour)

By default, `batch` scans the output directory for existing baselines and decides per row:

| Situation | What happens |
|-----------|-------------|
| Baseline already exists for this sample + group | **Extend** — existing IDs are kept, new IDs appended, old file renamed to `.old` |
| No baseline found for this sample + group | **Create new** — acts exactly like a fresh batch run |

You can freely mix new and existing samples in the same sheet. The counts in the sheet are always **additional** subjects to add on top of what already exists.

```bash
python idgenerator.py batch --input-file extra_samples.xlsx --output ./output
```

To force every row to be treated as brand new (ignoring any existing baselines), use `--fresh`:

```bash
python idgenerator.py batch --input-file samples.xlsx --fresh --output ./output
```

**`--input-dir`** lets you specify a different directory to search for existing baselines (defaults to `--output`). New random numbers are guaranteed unique across both old and new IDs.

**Example sheet combining new and existing samples:**

| SampleName | NCases | NControls |
|------------|--------|-----------|
| Sample001  | 20     | 30        | ← already exists → will be extended |
| Sample003  | 50     | 75        | ← new sample → will be created fresh |

---

### `followup` — generate follow-up visit IDs

Reads all current per-site IDS_IDT files from `per_site/` and produces IDS↔IDSVn pairs. The visit number is loaded from `study.cfg` (set via `init --visit`). Pass `--visit` on the CLI to override for a specific run.

```bash
# With visit number from study.cfg (recommended)
python idgenerator.py followup --output ./output

# Override visit number for this run only
python idgenerator.py followup --visit 3 --output ./output
```

Output structure:
```
output/
  IDS_IDSV{n}_ALL_N={total}_V={n}.txt   ← all sites merged (Track + Group columns)
  followup/
    IDS_IDSV{n}_T=…_G=…_N=…_V={n}.txt  ← one file per site/group
```

Output columns — per-site: `IDS | IDSVn | IDS128 | IDSVn128`  
Output columns — ALL: `IDS | IDSVn | IDS128 | IDSVn128 | Track | Group`

---

### `add-track` — create an empty baseline placeholder for a new track

```bash
python idgenerator.py add-track \
    --study  MyStudy \
    --track  TrackC \
    --output ./output
```

Creates header-only `.txt` files (`N=0`) ready to be extended later.

---

### `extend` — add new subjects to an existing baseline

```bash
python idgenerator.py extend \
    --study       MyStudy \
    --center      01 \
    --tracks      "TrackA:100,TrackB:200" \
    --new-samples "TrackA:20,TrackB:30" \
    --digits      5 \
    --blocks      CTNVX \
    --checksum    Damm_2004 \
    --input-dir   ./output \
    --output      ./output
```

New random numbers avoid all previously used values. Old baseline files are renamed to `.old`.

---

### `external` — create external-project IDs

Creates IDE IDs (one digit wider than the study IDs) linked to an existing IDS baseline.

```bash
python idgenerator.py external \
    --study       MyStudy \
    --center      01 \
    --ext-project ExtProj \
    --digits      5 \
    --blocks      CTNVX \
    --checksum    Damm_2004 \
    --input-dir   ./output \
    --output      ./output
```

Output columns: `IDS | IDE | IDS128 | IDE128`

---

## Checksum algorithms

| Name | Description |
|------|-------------|
| `none` | No check digit |
| `Simple_Parity` | Sum of character values mod 10 |
| `Weighted_Parity` | Sum of (character value × position) mod 10 |
| `Gumm_1986` | Gumm (1986) algorithm |
| `Damm_2004` | Damm (2004) algorithm *(default, recommended)* |

---

## Output file format

All output files are **tab-separated `.txt`** with a single header row. The `*128` columns contain Code 128 barcode-encoded strings.

**Directory layout after a full run:**
```
output/
  study.cfg                              ← study parameters (written by init)
  LogFile.txt                            ← timestamped audit trail
  IDP_IDT_ALL_N={total}_Baseline.txt     ← master: all sites, personal data + temp keys
  IDS_IDT_ALL_N={total}_Baseline.txt     ← master: all sites, study data
  IDS_IDSV{n}_ALL_N={total}_V={n}.txt   ← master: all sites, follow-up visit n
  per_site/
    IDP_IDT_T=…_G=…_N=…_Baseline.txt    ← per-site personal data (always written)
    IDS_IDT_T=…_G=…_N=…_Baseline.txt    ← per-site study data (always written)
    *.old                                ← superseded files when a site is extended
  followup/
    IDS_IDSV{n}_T=…_G=…_N=…_V={n}.txt  ← per-site follow-up files
```

| File type | Columns |
|-----------|---------|
| `IDP_IDT` per-site | `IDP`, `IDP128`, `IDT` |
| `IDS_IDT` per-site | `IDS`, `IDS128`, `IDT` |
| `*_ALL` combined | above + `Track`, `Group` |
| Follow-up per-site | `IDS`, `IDSVn`, `IDS128`, `IDSVn128` |
| Follow-up ALL | above + `Track`, `Group` |
| External | `IDS`, `IDE`, `IDS128`, `IDE128` |

Pass `--shuffle` to randomise row order in per-site IDS files (breaks positional re-linking of personal and study data). The master ALL files are always written regardless.

---

## Differences from the original

| Original (VB.NET) | This port (Python) |
|-------------------|--------------------|
| Windows only (WinForms) | Windows / macOS / Linux |
| GUI application | Command-line interface |
| Config saved as `Config.xml` | Config saved as `study.cfg` (JSON) via `init` command; loaded automatically on every subsequent run |
| Output written next to `.exe` | Output written to `--output` directory |
| 5 operations via radio buttons | 7 subcommands: `init`, `baseline`, `batch`, `followup`, `add-track`, `extend`, `external` |
| No batch/sample-sheet input | New `batch` command with case/control `G` block |
| No mixed new/extend in one operation | `batch --extend` auto-detects existing samples and adds to them; unknown samples are created fresh |
| Bug in `ExtendBaseline` (IDT overwritten with IDS value) | Fixed |

---

## Credits

**Original programme**

> Olden M, Holle R, Heid IM, Stark K.  
> *IDGenerator: unique identifier generator for epidemiologic or clinical studies.*  
> BMC Medical Research Methodology. 2016;16(1):103.  
> PMID: 27628043 · PMCID: PMC5024489 · DOI: [10.1186/s12874-016-0222-3](https://doi.org/10.1186/s12874-016-0222-3)

Source code and Windows binary: [Open Science Framework — osf.io/urs2g](https://osf.io/urs2g/)  
Department of Genetic Epidemiology, University of Regensburg, Germany.

**Python adaptation:** kaiyao28
