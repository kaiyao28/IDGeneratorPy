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

### Wave 1 — first batch of samples arrives

`wave1.xlsx` (or `.csv` / `.txt`):

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA      | 50     | 100       |
| SiteB      | 30     | 60        |

```bash
python idgenerator.py batch \
    --study      MyStudy \
    --center     01 \
    --input-file wave1.xlsx \
    --digits     5 \
    --blocks     CTGNVX \
    --checksum   Damm_2004 \
    --case-prefix    S \
    --control-prefix C \
    --output ./ids
```

This creates two files per site in `./ids/` (one IDP_IDT file per case/control group):
```
{ts}_MyStudy_IDP_IDT_T=SiteA_G=S_N=50_Baseline.txt    ← SiteA cases,    personal data
{ts}_MyStudy_IDP_IDT_T=SiteA_G=C_N=100_Baseline.txt   ← SiteA controls, personal data
... (same two files for SiteB)
```

To also generate the row-shuffled study-data file (IDS_IDT), add `--shuffle`:
```bash
python idgenerator.py batch ... --shuffle
```
With `--shuffle`, four files are produced per site instead of two.

---

### Wave 2 — more samples from existing sites, plus a brand-new site

`wave2.xlsx`:

| SampleName | NCases | NControls |
|------------|--------|-----------|
| SiteA      | 20     | 40        |
| SiteC      | 15     | 30        |

- **SiteA** already has a baseline → will be **extended** (20 new cases, 40 new controls appended; old files renamed `.old`)
- **SiteC** is new → will be **created fresh**

```bash
python idgenerator.py batch \
    --study      MyStudy \
    --center     01 \
    --input-file wave2.xlsx \
    --digits     5 \
    --blocks     CTGNVX \
    --checksum   Damm_2004 \
    --case-prefix    S \
    --control-prefix C \
    --extend \
    --input-dir  ./ids \
    --output     ./ids
```

The script auto-detects which sites already exist and handles each row accordingly. No manual bookkeeping needed. Every new random number is guaranteed unique across all previous waves.

---

### What each output file is for

| File | Who uses it | Contains |
|------|-------------|----------|
| `IDP_IDT` | Your team (coordinating center) | Personal data identifier + temporary key. Keep confidential. |
| `IDS_IDT` | Lab / analysts | Study data identifier + temporary key. Share for processing. Row order is randomised. |

Once data collection is complete and linkage is no longer needed, the IDT column can be deleted from the IDS file to make it fully anonymous.

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
# Wave 1 — fresh baseline
python idgenerator.py batch --study TestStudy --center 01 \
    --input-file test_full/samples.csv \
    --digits 5 --blocks CTGNVX --checksum Damm_2004 \
    --case-prefix S --control-prefix C --output test_full/ids

# Wave 2 — extend SiteA, create SiteC
python idgenerator.py batch --study TestStudy --center 01 \
    --input-file test_full/wave2.csv \
    --digits 5 --blocks CTGNVX --checksum Damm_2004 \
    --case-prefix S --control-prefix C \
    --extend --input-dir test_full/ids --output test_full/ids

# Wave 3 — new site, produce shuffled IDS file for the lab
python idgenerator.py batch --study TestStudy --center 01 \
    --input-file test_full/wave3.csv \
    --digits 5 --blocks CTGNVX --checksum Damm_2004 \
    --case-prefix S --control-prefix C --shuffle --output test_full/ids

# Follow-up visit 2 for SiteD (which has an IDS file from --shuffle above)
python idgenerator.py followup --study TestStudy --center 01 \
    --digits 5 --blocks CTGNVX --checksum Damm_2004 \
    --visit 2 --input-dir test_full/ids --output test_full/ids
```

After running, `test_full/ids/LogFile.txt` contains a full timestamped audit trail. Extended files are renamed `.old` and kept alongside the current version.

---

## Commands

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

**Output files** (one pair per sample × group):
```
{ts}_{study}_IDP_IDT_T={sample}_G=S_N={n}_Baseline.txt   ← cases,    unshuffled
{ts}_{study}_IDS_IDT_T={sample}_G=S_N={n}_Baseline.txt   ← cases,    row-shuffled
{ts}_{study}_IDP_IDT_T={sample}_G=C_N={n}_Baseline.txt   ← controls, unshuffled
{ts}_{study}_IDS_IDT_T={sample}_G=C_N={n}_Baseline.txt   ← controls, row-shuffled
```

---

#### `batch --extend` — add subjects to existing samples (or create new ones)

Pass the `--extend` flag when you want to top up samples that already have a baseline. In this mode the counts in the sheet are **additional** subjects to add, not totals.

```bash
python idgenerator.py batch \
    --study      MyStudy \
    --center     01 \
    --input-file extra_samples.xlsx \
    --digits     5 \
    --blocks     CTGNVX \
    --checksum   Damm_2004 \
    --extend \
    --input-dir  ./output \
    --output     ./output
```

Behaviour per row:

| Situation | What happens |
|-----------|-------------|
| Baseline already exists for this sample + group | **Extend** — existing IDs are kept, new IDs appended, old file renamed to `.old` |
| No baseline found for this sample + group | **Create new** — acts exactly like normal `batch` mode |

You can mix new and existing samples in the same sheet — the script handles each row automatically.

**Important:** `--input-dir` tells the script where to look for existing baseline files (defaults to `--output` if omitted). New random numbers are guaranteed unique across both old and new IDs.

**Example sheet combining new and existing samples:**

| SampleName | NCases | NControls |
|------------|--------|-----------|
| Sample001  | 20     | 30        | ← already exists → will be extended |
| Sample003  | 50     | 75        | ← new sample → will be created fresh |

---

### `followup` — generate follow-up visit IDs

Reads existing baseline IDS_IDT files and produces IDS↔IDSVn pairs for a new visit number. Works on files produced by both `baseline` and `batch`.

```bash
python idgenerator.py followup \
    --study     MyStudy \
    --center    01 \
    --digits    5 \
    --blocks    CTGNVX \
    --checksum  Damm_2004 \
    --visit     2 \
    --input-dir ./output \
    --output    ./output
```

Output columns: `IDS | IDSVn | IDS128 | IDSVn128`

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

All output files are **tab-separated `.txt`** with a single header row, matching the format of the original Windows application exactly.

| File type | Columns | When generated |
|-----------|---------|----------------|
| `IDP_IDT` | `IDP`, `IDP128`, `IDT` | Always (default) |
| `IDS_IDT` | `IDS`, `IDS128`, `IDT` | Only with `--shuffle` |
| Follow-up | `IDS`, `IDSVn`, `IDS128`, `IDSVn128` | `followup` command |
| External  | `IDS`, `IDE`, `IDS128`, `IDE128` | `external` command |

The `*128` columns contain Code 128 barcode-encoded strings.

By default, only the `IDP_IDT` file is written per sample. Pass `--shuffle` to also produce the `IDS_IDT` file with row order randomised (which breaks positional re-linking of personal and study data).

---

## Differences from the original

| Original (VB.NET) | This port (Python) |
|-------------------|--------------------|
| Windows only (WinForms) | Windows / macOS / Linux |
| GUI application | Command-line interface |
| Config saved as `Config.xml` | All parameters passed as flags |
| Output written next to `.exe` | Output written to `--output` directory |
| 5 operations via radio buttons | 6 subcommands: `baseline`, `batch`, `followup`, `add-track`, `extend`, `external` |
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
