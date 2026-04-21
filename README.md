# IDGeneratorPy

A cross-platform Python adaptation of [idGenerator](https://github.com/mpmky/idGenerator) — a randomized clinical study ID generator originally written in VB.NET / Windows Forms by the Genetic Epidemiology group at the University of Regensburg (2016).

The original programme runs on Windows only. This port re-implements the same generation logic, checksum algorithms, and output file formats as a plain Python 3 command-line script that runs on Windows, macOS, and Linux with no dependencies beyond the standard library.

---

## How it works

Each subject receives three linked IDs generated from separate random pools:

| ID | Pool range (5-digit example) | Purpose |
|----|------------------------------|---------|
| **IDP** (Principal) | 10 000 – 39 999 | Unblinded — kept by the principal investigator |
| **IDS** (Scrambled) | 40 000 – 69 999 | Sent to the lab — row order is shuffled to break the IDP↔IDS link |
| **IDT** (Tracking) | 70 000 – 99 999 | Shared between IDP and IDS files as the re-linkage key |

IDs are assembled from configurable **building blocks** (`--blocks`):

| Block | Meaning |
|-------|---------|
| `C` | Study center code |
| `T` | Track / sample name |
| `G` | Group label (e.g. `S` for cases, `C` for controls) — used with `batch` command |
| `N` | Unique random number |
| `V` | Visit number (`0` for IDP, `1` for IDS/IDT at baseline) |
| `X` | Check digit |

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

| File type | Columns |
|-----------|---------|
| `IDP_IDT` | `IDP`, `IDP128`, `IDT` |
| `IDS_IDT` | `IDS`, `IDS128`, `IDT` |
| Follow-up | `IDS`, `IDSVn`, `IDS128`, `IDSVn128` |
| External  | `IDS`, `IDE`, `IDS128`, `IDE128` |

The `*128` columns contain Code 128 barcode-encoded strings.

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
