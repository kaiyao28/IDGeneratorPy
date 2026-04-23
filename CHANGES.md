# Changes from the original IDGenerator

This document records every difference between this Python port and the original VB.NET programme (Olden et al. 2016, University of Regensburg). The original source is available at [osf.io/urs2g](https://osf.io/urs2g/).

---

## Platform and interface

| Original | This port |
|----------|-----------|
| Windows only — WinForms GUI | Windows / macOS / Linux — command-line interface |
| 5 operations selected via radio buttons | 7 subcommands: `init`, `baseline`, `batch`, `followup`, `add-track`, `extend`, `external` |
| Study parameters entered in GUI each session | `init` writes `study.cfg` once; all subsequent commands load it automatically |
| Config persisted as `Config.xml` | Config persisted as `study.cfg` (JSON) |

---

## New building block: `R` (recruitment site)

The original building block set had `T` serve double duty — in standard batch mode it embedded the recruitment site name; in multi-track mode it embedded the data-track abbreviation. This made the two cases inconsistent and made the ID ambiguous at a glance.

A new `R` block has been added for the recruitment site name (`SampleName` from the input sheet). `T` retains its original meaning in standard mode (full site name) for backward compatibility, but in multi-track mode `T` holds the data-track abbreviation and `R` holds the site name:

```
Standard batch   --blocks CTGNVX  →  01SiteAS123451X   (T = site)
Multi-track      --blocks CRTNVX  →  01SiteAG123451X   (R = site, T = track abbreviation)
```

Existing studies using `--blocks CTNVX` in multi-track mode continue to work unchanged (T = track abbreviation, site in filename only). Add `R` to the blocks string when you want the site name visible in every ID.

---

## New building block: `S` (study name prefix)

The original building block set was `C`, `T`, `G`, `N`, `V`, `X`. This port adds `S`, which embeds the study name (`--study`) as a prefix at the start of every ID:

```
--blocks CTNVX   →  01SiteA123451X
--blocks SCTNVX  →  MyStudy01SiteA123451X
```

`S` is optional. Include it when IDs from different studies may appear in the same dataset or file. All three ID types (IDP, IDS, IDT) receive the same prefix — the `V` block distinguishes them (`0` = IDP, `1` = IDS/IDT).

The original programme had no equivalent; the study name appeared only in filenames.

---

## New commands

### `init`
Saves study parameters to `study.cfg` so they do not need to be re-entered on every run. Supports `--study`, `--center`, `--digits`, `--blocks`, `--checksum`, `--case-prefix`, `--control-prefix`, `--visit`, `--output`.

Two additional parameters support the multi-track anonymised cohort workflow:
- **`--tracks`** — comma-separated list of data track names (e.g. `Genetics,Phenotype`). Saved to `study.cfg` and auto-loaded by every subsequent `batch` call; no need to repeat it per wave.
- **`--anon`** — marks the cohort as anonymised: multi-track `batch` draws IDs from the IDS pool (40 000–69 999) and labels columns `IDS_*` instead of the IDP pool. Use when there is no personal data to track.

### `batch`
Sheet-based ID generation for multi-site, multi-group studies. Reads a sample sheet (`.xlsx`, `.csv`, `.txt`) with `SampleName / NCases / NControls` columns and generates one IDP and one IDS file per site × group in a single run. Not present in the original.

Key `batch` capabilities not in the original:
- **Flexible column names** — case-insensitive aliases accepted (`NCases`, `Cases`, `N_Cases`, etc.)
- **Auto-extend** — for each row the script checks whether a baseline already exists and extends it automatically; sites not yet seen are created fresh. Mixed new + extend in one run is fully supported.
- **`--fresh` flag** — forces all rows to be treated as new regardless of what is on disk.
- **`--shuffle` flag** — randomises row order in per-site IDS output. Breaks positional re-identification when the file is shared outside its context.
- **`--seed` flag** — fixes the random seed for reproducible output. Seed is recorded in `LogFile.txt`.
- **Multi-format input** — `.xlsx` / `.xls` (requires `openpyxl`), `.csv`, `.tsv`, `.txt` all accepted natively.
- **`--tracks` flag** — multi-track mode: the sheet defines sites and counts; `--tracks` defines what IDS columns every participant receives (`IDS_Genetics`, `IDS_Phenotype`, etc.). Tracks must be declared before the first batch run — they cannot be added retroactively to existing participants.
- **`--samplesize` flag** — inline count mode: pass participant counts directly on the command line instead of a sheet (`--samplesize 50 80` for 50 cases and 80 controls). No input file needed.
- **Track abbreviation** — in multi-track mode the T block holds the first character of the data-track name (e.g. `G` for Genetics, `P` for Phenotype). Column headers and filenames always use the full name. Use the new `R` block alongside `T` to also embed the recruitment site name in every ID (`--blocks CRTNVX`). Sites and data tracks are independent dimensions — see REFERENCE.md.

### `add-track`
Creates a header-only (`N=0`) baseline placeholder for a new track, ready to be extended in a later wave.

---

## Changes to existing behaviour

### `V` block redefined as ID-type flag

In the original programme the `V` building block was a mutable visit counter — it was `1` at baseline and incremented to `2`, `3`, … at each follow-up visit. This port redefines `V` as a fixed **ID-type flag**:

- `V = 0` → the ID is an **IDP** (personal data)
- `V = 1` → the ID is an **IDS** (study data) or **IDT** (linkage key)

The value never changes after the ID is generated. Visit information is encoded separately via the `V2_` prefix on the full baseline IDS (see below). This makes it unambiguous whether a given string is a personal or study ID, even without the filename for context.

### Follow-up IDs — prefix approach

The original programme changed a single digit inside the ID to encode the visit number (e.g. the visit field `V` went from `1` to `2`). This created two problems:

1. Baseline and visit-2 IDs were nearly identical — easy to mix up on a label or in a spreadsheet.
2. Visit numbers ≥ 10 would overflow the single-digit field and silently corrupt the ID.

This port uses a prefix instead:

```
Baseline IDS  :  01SiteAS123451X
Visit 2 IDSV2 :  V2_01SiteAS123451X
Visit 3 IDSV3 :  V3_01SiteAS123451X
```

The prefix is unambiguous at a glance, the full baseline ID is embedded so the link is always traceable, no new random numbers are drawn, and visit numbers can be any positive integer with no upper limit.

### Follow-up does not consume pool numbers

Because follow-up IDs are derived from existing baseline IDS values (prefix only), they draw nothing from the random number pools. Pool capacity is determined entirely by the number of enrolled participants across all `batch` / `baseline` waves. This means a study with 20,000 participants at 5 digits (pool limit ≈ 30,000) can run unlimited follow-up visits without approaching that limit.

### Barcode columns removed from master analytical files

Code 128 barcode strings occasionally contain a space character (when the check value equals 0, which maps to ASCII 32). This causes silent data loss in Excel VLOOKUP and breaks R `merge()` and `trimws()`.

The fix splits barcode columns by use:
- **Per-site files** (for tube label printing) keep `*128` barcode columns.
- **Master ALL files** (for data analysis) contain only plain IDs — no barcode columns.

| File type | Columns |
|-----------|---------|
| `IDP_IDT` per-site | `IDP`, `IDP128`, `IDT` |
| `IDS_IDT` per-site | `IDS`, `IDS128`, `IDT` |
| `IDP_IDT` ALL master | `IDP`, `IDT`, `Track`, `Group` |
| `IDS_IDT` ALL master | `IDS`, `IDT`, `Track`, `Group` |
| Follow-up per-site | `IDS`, `IDSVn`, `IDS128`, `IDSVn128` |
| Follow-up ALL | `IDS`, `IDSVn`, `Track`, `Group` |

### Filename conventions

- Timestamps use date only (`YYYYMMDD`) — no time component.
- Per-site files carry a `_Baseline` or `_Extended` suffix to distinguish first creation from subsequent extensions.
- Master `_ALL_` files carry neither suffix (they are always rebuilt to the current state after every run).
- Superseded per-site files are renamed `.old` rather than deleted, preserving the full audit trail.

### `study.cfg` auto-load

All commands (except `init`) automatically load parameters from `study.cfg` if it exists in the output directory. CLI flags always override saved values. The original required manual re-entry of parameters for every session.

---

## Bug fixes

**ExtendBaseline wrote IDS values into the IDT column.** In the original VB.NET code, the extend operation incorrectly copied IDS values into the IDT field when appending new subjects. This left the extended file with corrupted IDT values. Fixed in this port.

**Multi-track `batch` ignored NControls.** The `_generate_batch_multitrack` function read only `NCases` from each sheet row and discarded `NControls`. Sites with a case/control split (e.g. SiteB with 150 cases + 75 controls) produced only 150 IDS IDs instead of 225. Fixed: `n_participants = n_cases + n_controls`.

**Multi-track `batch` produced malformed IDs when `--blocks` contained `G`.** The G building block requires a case/control group argument. In multi-track mode every participant is treated as a single unit with no group split, so `group` was always passed as an empty string. This silently shrank the ID (missing G character) and shifted all subsequent field positions (N, V, X), breaking the extend logic. Fixed: `G` is stripped from `--blocks` at the start of `_generate_batch_multitrack`. Use `--blocks CTNVX` for multi-track anonymised batch runs.

**`--anon` without `--tracks` fell to the standard `generate_batch` path.** When `--anon` was saved in `study.cfg` but no `--tracks` were declared, the batch dispatch routed to the standard case/control path which always generates IDP (personal data IDs). Fixed: a dedicated branch now routes `--anon` with no tracks to `_generate_batch_multitrack` with an empty track list, producing a single plain `IDS` column.

---

## What has not changed

- The three-pool ID design (IDP / IDS / IDT), pool boundaries, and the anonymisation principle are identical to the original.
- All checksum algorithms (`Simple_Parity`, `Weighted_Parity`, `Gumm_1986`, `Damm_2004`) are reproduced faithfully.
- Building block definitions (`C`, `T`, `G`, `N`, `V`, `X`) and their assembly order are unchanged.
- The `external` command logic and IDE ID format are unchanged.
