#!/usr/bin/env python3
"""
idGenerator - Cross-platform clinical study ID generator
Ported from idGenerator v1.0.0 (VB.NET / WinForms)
(C) 2016 Genetic Epidemiology, University of Regensburg

Usage examples
--------------
# Generate a fresh baseline (2 tracks, 100 + 200 subjects, 5-digit IDs):
  python idgenerator.py baseline \\
      --study MyStudy --center 01 \\
      --tracks "TrackA:100,TrackB:200" \\
      --digits 5 --blocks CTNVX --checksum Damm_2004 \\
      --output ./output

# Batch-generate baseline from a sample sheet (cases & controls per sample):
  python idgenerator.py batch \\
      --study MyStudy --center 01 \\
      --input-file samples.xlsx \\
      --digits 5 --blocks CTGNVX --checksum Damm_2004 \\
      --case-prefix S --control-prefix C \\
      --output ./output

  Input file columns (txt/csv/tsv/xlsx/xls):
    SampleName   NCases   NControls
    Sample001    100      200
    Sample002    50       75

  Output files produced per sample:
    {ts}_{study}_IDP_IDT_T={sample}_G=S_N={cases}_Baseline.txt
    {ts}_{study}_IDS_IDT_T={sample}_G=S_N={cases}_Baseline.txt
    {ts}_{study}_IDP_IDT_T={sample}_G=C_N={controls}_Baseline.txt
    {ts}_{study}_IDS_IDT_T={sample}_G=C_N={controls}_Baseline.txt

# Generate follow-up visit 2 from baseline files:
  python idgenerator.py followup \\
      --study MyStudy --center 01 \\
      --digits 5 --blocks CTNVX --checksum Damm_2004 \\
      --visit 2 --input-dir ./output --output ./output

# Add a new empty track placeholder:
  python idgenerator.py add-track \\
      --study MyStudy --track TrackC --output ./output

# Extend existing baseline with new subjects:
  python idgenerator.py extend \\
      --study MyStudy --center 01 \\
      --tracks "TrackA:100,TrackB:200" \\
      --new-samples "TrackA:20,TrackB:30" \\
      --digits 5 --blocks CTNVX --checksum Damm_2004 \\
      --input-dir ./output --output ./output

# Create external IDs linked to an existing baseline:
  python idgenerator.py external \\
      --study MyStudy --center 01 --ext-project ExtProj \\
      --digits 5 --blocks CTNVX --checksum Damm_2004 \\
      --input-dir ./output --output ./output

Building blocks (--blocks):
  C = Study center code
  T = Track / sample name
  G = Group (case prefix vs control prefix — use with 'batch' command)
  N = Unique random number
  V = Visit number  (IDP=0, IDS/IDT=1, follow-ups=specified)
  X = Check digit

  Recommended for batch mode: CTGNVX
  Recommended for single-track mode: CTNVX

Checksum algorithms (--checksum):
  none            No check digit
  Simple_Parity   Sum of char values mod 10
  Weighted_Parity Sum of (char_value * position) mod 10
  Gumm_1986       Gumm 1986 algorithm
  Damm_2004       Damm 2004 algorithm (default)

ID types (Olden et al. 2016, BMC Med Res Methodol):
  IDP = Personal data identifier  — links to name/address/DOB; restricted to study personnel; visit=0
  IDS = Study data identifier     — links to scientific data; for study analysts; row order randomised
  IDT = Temporary identifier      — temporary linkage key between IDP and IDS; can be deleted for anonymisation
  IDE = External identifier       — k+1 digits; links an external project to existing IDS records

Output files (tab-separated .txt):
  {ts}_{study}_IDP_IDT_T={track}_N={n}_Baseline.txt  — IDP/IDT pairs, unshuffled (always written)
  {ts}_{study}_IDS_IDT_T={track}_N={n}_Baseline.txt  — IDS/IDT pairs, row-shuffled (written only with --shuffle)
"""

import argparse
import csv
import os
import random
import sys
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# CHECKSUM ALGORITHMS
# ─────────────────────────────────────────────────────────────────────────────

def _id_to_numstr(id_str: str) -> str:
    """Strip [CHECKSUM], replace non-digits with ASCII codes — for checksum input."""
    s = id_str.replace("[CHECKSUM]", "")
    result = ""
    for ch in s:
        result += ch if ch.isdigit() else str(ord(ch))
    return result


def checksum_simple_parity(id_str: str) -> int:
    s = id_str.replace("[CHECKSUM]", "")
    total = sum(int(ch) if ch.isdigit() else ord(ch) for ch in s)
    return total % 10


def checksum_weighted_parity(id_str: str) -> int:
    s = id_str.replace("[CHECKSUM]", "")
    total = sum(
        (int(ch) if ch.isdigit() else ord(ch)) * (i + 1)
        for i, ch in enumerate(s)
    )
    return total % 10


# Gumm 1986 — addArr(H,V) = _GUMM_ADD[V][H], so sum_new = _GUMM_ADD[aux][sum]
_GUMM_ADD = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# tauArr(H,V) = _GUMM_TAU[V][H], so aux = _GUMM_TAU[(k-1)%10][dig-1]
_GUMM_TAU = [
    [0, 4, 3, 2, 1, 8, 9, 5, 6, 7],
    [0, 1, 2, 3, 4, 6, 7, 8, 9, 5],
    [0, 4, 3, 2, 1, 9, 5, 6, 7, 8],
    [0, 1, 2, 3, 4, 7, 8, 9, 5, 6],
    [0, 4, 3, 2, 1, 5, 6, 7, 8, 9],
    [1, 0, 3, 2, 4, 8, 9, 5, 6, 7],
    [4, 0, 2, 3, 1, 6, 7, 8, 9, 5],
    [1, 0, 3, 2, 4, 9, 5, 6, 7, 8],
    [4, 0, 2, 3, 1, 7, 8, 9, 5, 6],
    [1, 0, 3, 2, 4, 5, 6, 7, 8, 9],
]


def _gumm_check_digit(num: int) -> int:
    s = str(num)
    acc = 0
    number = num
    for k in range(1, len(s) + 1):
        dig = (number % 10) + 1
        aux = _GUMM_TAU[(k - 1) % 10][dig - 1]
        acc = _GUMM_ADD[aux][acc]
        number //= 10
    if 0 < acc < 5:
        acc = 5 - acc
    return acc


def checksum_gumm_1986(id_str: str) -> int:
    num_str = _id_to_numstr(id_str)
    num = int(num_str) if num_str.isdigit() and num_str else 0
    return _gumm_check_digit(num)


# Damm 2004 — DammTransposedArr(iD, dig) = _DAMM[iD][dig]
_DAMM = [
    [0, 3, 1, 7, 5, 9, 8, 6, 4, 2],
    [7, 0, 9, 2, 1, 5, 4, 8, 6, 3],
    [4, 2, 0, 6, 8, 7, 1, 3, 5, 9],
    [1, 7, 5, 0, 9, 8, 3, 4, 2, 6],
    [6, 1, 2, 3, 0, 4, 5, 9, 7, 8],
    [3, 6, 7, 4, 2, 0, 9, 5, 8, 1],
    [5, 8, 6, 9, 7, 2, 0, 1, 3, 4],
    [8, 9, 4, 5, 3, 6, 2, 0, 1, 7],
    [9, 4, 3, 8, 6, 1, 7, 2, 0, 5],
    [2, 5, 8, 1, 4, 3, 6, 7, 9, 0],
]


def _damm_check_digit(num: int) -> int:
    interim = 0
    for ch in str(num):
        interim = _DAMM[interim][int(ch)]
    return interim


def checksum_damm_2004(id_str: str) -> int:
    num_str = _id_to_numstr(id_str)
    num = int(num_str) if num_str.isdigit() and num_str else 0
    return _damm_check_digit(num)


CHECKSUMS = {
    "none":             lambda _: 0,
    "Simple_Parity":    checksum_simple_parity,
    "Weighted_Parity":  checksum_weighted_parity,
    "Gumm_1986":        checksum_gumm_1986,
    "Damm_2004":        checksum_damm_2004,
}


# ─────────────────────────────────────────────────────────────────────────────
# CODE 128 BARCODE
# ─────────────────────────────────────────────────────────────────────────────

_CODE128_SPECIAL = {
    95: 180, 96: 228, 97: 246, 98: 252,
    99: 196, 100: 214, 101: 220, 102: 181,
}


def format_code128(s: str) -> str:
    total = 104
    for i, ch in enumerate(s, 1):
        total += (ord(ch) - 32) * i
    cs = total % 103
    checkchar = _CODE128_SPECIAL.get(cs, cs + 32 if cs <= 94 else -1)
    if checkchar == -1:
        return ""
    return chr(193) + s + chr(checkchar) + chr(200)


# ─────────────────────────────────────────────────────────────────────────────
# ID ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def build_id(blocks: str, center: str, track: str, number: int, visit,
             checksum_fn, *, group: str = "") -> str:
    """
    Assemble an ID string from building blocks and compute its check digit.
    G block requires `group` keyword argument (e.g. "S" for cases, "C" for controls).
    """
    parts = []
    for bb in blocks:
        if   bb == "C": parts.append(center)
        elif bb == "T": parts.append(track)
        elif bb == "G": parts.append(group)
        elif bb == "N": parts.append(str(number))
        elif bb == "V": parts.append(str(visit))
        elif bb == "X": parts.append("[CHECKSUM]")
    raw = "".join(parts)
    return raw.replace("[CHECKSUM]", str(checksum_fn(raw)))


def field_start(blocks: str, field: str, center_len: int, track_len: int,
                digits: int, group_len: int = 0) -> int:
    """Return the 0-based character position where `field` starts inside a built ID."""
    pos = 0
    for bb in blocks:
        if bb == field:
            return pos
        if   bb == "C": pos += center_len
        elif bb == "T": pos += track_len
        elif bb == "G": pos += group_len
        elif bb == "N": pos += digits
        elif bb in ("V", "X"): pos += 1
    return -1


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_param_from_filename(path: str, param: str) -> str:
    """Extract the value of PARAM=VALUE from a filename stem."""
    name = Path(path).stem
    key = f"{param}="
    idx = name.find(key)
    if idx == -1:
        return ""
    start = idx + len(key)
    end = name.find("_", start)
    val = name[start:end] if end != -1 else name[start:]
    return "" if val == "none" else val


def count_data_lines(filepath: str) -> int:
    """Count non-header lines in a tab-separated file."""
    with open(filepath, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip()]
    return max(0, len(lines) - 1)


def _unique_randoms(lo: int, hi: int, count: int, excluded: set) -> list:
    """Draw `count` unique random integers from [lo, hi] avoiding `excluded`."""
    result = []
    used = set(excluded)
    for _ in range(count):
        n = random.randint(lo, hi)
        while n in used:
            n = random.randint(lo, hi)
        used.add(n)
        result.append(n)
    return result


def _id_pools(digits: int):
    """Return (lo_idp, hi_idp, lo_ids, hi_ids, lo_idt, hi_idt) for a given digit count."""
    lo_idp = 1 * 10 ** (digits - 1)
    hi_idp = 4 * 10 ** (digits - 1) - 1
    lo_ids = 4 * 10 ** (digits - 1)
    hi_ids = 7 * 10 ** (digits - 1) - 1
    lo_idt = 7 * 10 ** (digits - 1)
    hi_idt = 10 * 10 ** (digits - 1) - 1
    return lo_idp, hi_idp, lo_ids, hi_ids, lo_idt, hi_idt


def _write_tsv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(header)
        w.writerows(rows)


# ─────────────────────────────────────────────────────────────────────────────
# INPUT FILE READER  (txt / csv / tsv / xlsx / xls)
# ─────────────────────────────────────────────────────────────────────────────

# Accepted header aliases (lower-cased)
_SAMPLE_ALIASES  = {"samplename", "sample", "sample_name", "name", "id"}
_CASES_ALIASES   = {"ncases", "cases", "n_cases", "case", "ncase", "cases_n"}
_CONTROLS_ALIASES = {"ncontrols", "controls", "n_controls", "control", "ncontrol",
                     "controls_n", "ctrl", "nctrl"}


def _normalise_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("-", "_")


def _find_col(headers: list, aliases: set) -> int:
    """Return the 0-based index of the first header matching any alias, or -1."""
    for i, h in enumerate(headers):
        if _normalise_header(h) in aliases:
            return i
    return -1


def read_sample_sheet(filepath: str) -> list:
    """
    Read a sample sheet and return a list of (sample_name, n_cases, n_controls).

    Supported formats: .txt  .csv  .tsv  (tab or comma separated)
                       .xlsx  .xls       (requires openpyxl / xlrd)

    Expected columns (header names are flexible, case-insensitive):
      SampleName  |  NCases  |  NControls

    Rows with blank sample names or zero totals are silently skipped.
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext in (".xlsx", ".xls"):
        rows = _read_excel(path, ext)
    else:
        rows = _read_text(path)

    if not rows:
        raise ValueError(f"No data rows found in {filepath}")

    # Detect header vs positional
    first = rows[0]
    sample_col = _find_col(first, _SAMPLE_ALIASES)
    cases_col  = _find_col(first, _CASES_ALIASES)
    ctrl_col   = _find_col(first, _CONTROLS_ALIASES)

    if sample_col >= 0 and cases_col >= 0 and ctrl_col >= 0:
        data_rows = rows[1:]   # first row is a header
    elif len(first) >= 3:
        # Assume positional: col 0 = name, col 1 = cases, col 2 = controls
        sample_col, cases_col, ctrl_col = 0, 1, 2
        data_rows = rows
        # Skip if first row looks like a header (non-numeric in col 1)
        try:
            int(str(first[cases_col]).strip())
        except ValueError:
            data_rows = rows[1:]
    else:
        raise ValueError(
            f"Cannot interpret columns in {filepath}. "
            "Expected headers: SampleName, NCases, NControls"
        )

    result = []
    for i, row in enumerate(data_rows, 1):
        if len(row) <= max(sample_col, cases_col, ctrl_col):
            continue
        name    = str(row[sample_col]).strip()
        n_cases = str(row[cases_col]).strip()
        n_ctrl  = str(row[ctrl_col]).strip()
        if not name:
            continue
        try:
            n_cases = int(float(n_cases))
            n_ctrl  = int(float(n_ctrl))
        except ValueError:
            print(f"  Warning: skipping row {i} — non-numeric counts: {row}")
            continue
        if n_cases < 0 or n_ctrl < 0:
            print(f"  Warning: skipping row {i} — negative counts: {row}")
            continue
        result.append((name, n_cases, n_ctrl))

    return result


def _read_text(path: Path) -> list:
    """Read a plain-text file (csv/tsv/txt) into a list of row lists."""
    with open(path, encoding="utf-8-sig") as f:
        sample = f.read(4096)
    dialect = csv.Sniffer().sniff(sample, delimiters="\t,;")
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, dialect)
        return [row for row in reader if any(c.strip() for c in row)]


def _read_excel(path: Path, ext: str) -> list:
    """Read an Excel file into a list of row lists. Requires openpyxl (xlsx) or xlrd (xls)."""
    if ext == ".xlsx":
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                "openpyxl is required to read .xlsx files.\n"
                "Install it with:  pip install openpyxl\n"
                "Or save your file as .csv / .txt and use that instead."
            )
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [("" if c is None else str(c)) for c in row]
            if any(c.strip() for c in cells):
                rows.append(cells)
        wb.close()
        return rows

    else:  # .xls
        try:
            import xlrd
        except ImportError:
            raise ImportError(
                "xlrd is required to read .xls files.\n"
                "Install it with:  pip install xlrd\n"
                "Or save your file as .csv / .txt and use that instead."
            )
        wb = xlrd.open_workbook(str(path))
        ws = wb.sheet_by_index(0)
        rows = []
        for r in range(ws.nrows):
            cells = [str(ws.cell_value(r, c)) for c in range(ws.ncols)]
            if any(c.strip() for c in cells):
                rows.append(cells)
        return rows


# ─────────────────────────────────────────────────────────────────────────────
# SHARED BASELINE WRITER  (used by both 'baseline' and 'batch')
# ─────────────────────────────────────────────────────────────────────────────

def _write_baseline_for_track(study, center, track_name, group, track_n,
                               idp_nums, ids_nums, idt_nums,
                               blocks, checksum_fn, out, ts, *, shuffle=False):
    """
    Build full IDs for one track/group combination and write output files.
    Always writes IDP_IDT (unshuffled). Writes IDS_IDT (row-shuffled) only when shuffle=True.
    Returns (idp_filepath, ids_filepath_or_None).
    """
    idp_ids = [build_id(blocks, center, track_name, n, 0, checksum_fn, group=group) for n in idp_nums]
    idt_ids = [build_id(blocks, center, track_name, n, 1, checksum_fn, group=group) for n in idt_nums]
    idp128  = [format_code128(x) for x in idp_ids]

    g_tag = f"_G={group}" if group else ""

    idp_file = out / f"{ts}_{study}_IDP_IDT_T={track_name}{g_tag}_N={track_n}_Baseline.txt"
    _write_tsv(idp_file, ["IDP", "IDP128", "IDT"], zip(idp_ids, idp128, idt_ids))

    if not shuffle:
        return idp_file, None

    ids_ids = [build_id(blocks, center, track_name, n, 1, checksum_fn, group=group) for n in ids_nums]
    ids128  = [format_code128(x) for x in ids_ids]
    order = list(range(track_n))
    random.shuffle(order)
    ids_file = out / f"{ts}_{study}_IDS_IDT_T={track_name}{g_tag}_N={track_n}_Baseline.txt"
    _write_tsv(ids_file, ["IDS", "IDS128", "IDT"],
               ((ids_ids[i], ids128[i], idt_ids[i]) for i in order))

    return idp_file, ids_file


# ─────────────────────────────────────────────────────────────────────────────
# F1. GENERATE BASELINE IDs
# ─────────────────────────────────────────────────────────────────────────────

def generate_baseline(study, center, tracks, digits, blocks, checksum_name, output_dir, shuffle=False):
    """
    Generate a fresh baseline for a list of tracks.
    tracks : list of (track_name: str, sample_count: int)
    """
    checksum_fn = CHECKSUMS[checksum_name]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total_n = sum(n for _, n in tracks)
    max_possible = (10 ** digits - 10 ** (digits - 1) - 3) // 3
    if digits == 10:
        max_possible = 2_147_483_647

    if total_n > max_possible:
        print(f"ERROR: {total_n} IDs requested but maximum for {digits} digits is {max_possible}.")
        return False

    lo_idp, hi_idp, lo_ids, hi_ids, lo_idt, hi_idt = _id_pools(digits)
    print(f"ID-P pool : {lo_idp} – {hi_idp}")
    print(f"ID-S pool : {lo_ids} – {hi_ids}")
    print(f"ID-T pool : {lo_idt} – {hi_idt}")
    print(f"Generating {total_n} IDs across {len(tracks)} track(s)…")

    idp_nums = _unique_randoms(lo_idp, hi_idp, total_n, set())
    ids_nums = _unique_randoms(lo_ids, hi_ids, total_n, set())
    idt_nums = _unique_randoms(lo_idt, hi_idt, total_n, set())

    ts = timestamp()
    pos = 0
    for track_name, track_n in tracks:
        idp_file, ids_file = _write_baseline_for_track(
            study, center, track_name, "",
            track_n,
            idp_nums[pos:pos + track_n],
            ids_nums[pos:pos + track_n],
            idt_nums[pos:pos + track_n],
            blocks, checksum_fn, out, ts,
            shuffle=shuffle,
        )
        print(f"  [{track_name}] {track_n} IDs  →  {idp_file.name}")
        if ids_file:
            print(f"                         {ids_file.name}")
        pos += track_n

    print("Done.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# BATCH BASELINE  (sample sheet with cases + controls)
# ─────────────────────────────────────────────────────────────────────────────

def _read_existing_nums(ids_file: Path, idp_file: Path, blocks: str,
                        center: str, track_name: str, group: str, digits: int):
    """
    Read the numeric N-field values from an existing IDS_IDT / IDP_IDT baseline pair.
    Returns (idp_nums, ids_nums_matched, idt_nums, existing_count).
    IDS numbers are cross-referenced via IDT so they align positionally with IDP.
    """
    len_c = len(center)
    len_t = len(track_name)
    len_g = len(group)
    pos_n = field_start(blocks, "N", len_c, len_t, digits, group_len=len_g)

    # IDS file: build idt_num → ids_num lookup
    idt_to_ids = {}
    with open(ids_file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            if not row:
                continue
            ids_n = int(row[0][pos_n:pos_n + digits]) if pos_n >= 0 else 0
            idt_n = int(row[2][pos_n:pos_n + digits]) if pos_n >= 0 else 0
            idt_to_ids[idt_n] = ids_n

    # IDP file: ordered list of (idp_num, idt_num)
    idp_nums, idt_nums = [], []
    with open(idp_file, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            if not row:
                continue
            idp_nums.append(int(row[0][pos_n:pos_n + digits]) if pos_n >= 0 else 0)
            idt_nums.append(int(row[2][pos_n:pos_n + digits]) if pos_n >= 0 else 0)

    ids_nums_matched = []
    for idt_n in idt_nums:
        if idt_n not in idt_to_ids:
            raise ValueError(
                f"IDT value {idt_n} found in IDP file but not in IDS file. "
                "Ensure both files are from the same baseline run."
            )
        ids_nums_matched.append(idt_to_ids[idt_n])

    return idp_nums, ids_nums_matched, idt_nums, len(idp_nums)


def _find_baseline_pair(study: str, sample_name: str, group: str,
                        search_dir: Path):
    """
    Return (ids_file, idp_file) for an existing baseline, or (None, None) if not found.
    Matches the most recent file when multiple timestamps exist.
    """
    g_tag = f"_G={group}" if group else ""
    ids_matches = sorted(search_dir.glob(
        f"*{study}_IDS_IDT_T={sample_name}{g_tag}_*_Baseline.txt"
    ))
    idp_matches = sorted(search_dir.glob(
        f"*{study}_IDP_IDT_T={sample_name}{g_tag}_*_Baseline.txt"
    ))
    if ids_matches and idp_matches:
        return ids_matches[-1], idp_matches[-1]
    return None, None


def generate_batch(study, center, input_file, digits, blocks, checksum_name,
                   case_prefix, control_prefix, output_dir,
                   extend_mode=False, input_dir=None, shuffle=False):
    """
    Read a sample sheet and generate one baseline per sample×group.

    Default mode (extend_mode=False)
    ---------------------------------
    Every sample in the sheet is treated as brand new.
    Counts = total subjects to generate.

    Extend mode (extend_mode=True, --extend flag)
    ----------------------------------------------
    Counts = ADDITIONAL subjects to add on top of any existing baseline.
    - If a baseline already exists for that sample+group in input_dir:
        existing IDs are preserved, new ones are appended, old files renamed to .old.
    - If no baseline exists for that sample+group:
        new files are created from scratch (same as default mode).

    In both modes random numbers are drawn globally, guaranteeing uniqueness across
    every sample, group, and existing baseline in the same run.
    """
    checksum_fn = CHECKSUMS[checksum_name]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    inp = Path(input_dir) if input_dir else out

    print(f"Reading sample sheet: {input_file}")
    try:
        samples = read_sample_sheet(input_file)
    except (ValueError, ImportError) as e:
        print(f"ERROR: {e}")
        return False

    if not samples:
        print("ERROR: No valid samples found in input file.")
        return False

    lo_idp, hi_idp, lo_ids, hi_ids, lo_idt, hi_idt = _id_pools(digits)

    # ── Classify each sample×group and collect existing numbers ──────────────
    # Each entry: dict with keys sample_name, group_prefix, group_label,
    #   add_n, mode ("new"|"extend"), and optionally existing_* fields.
    plan = []
    used_idp, used_ids, used_idt = set(), set(), set()

    for sample_name, n_cases, n_controls in samples:
        for group_label, add_n, group_prefix in [
            ("cases",    n_cases,    case_prefix),
            ("controls", n_controls, control_prefix),
        ]:
            if add_n == 0:
                continue

            entry = dict(
                sample_name=sample_name,
                group_prefix=group_prefix,
                group_label=group_label,
                add_n=add_n,
            )

            if extend_mode:
                ids_f, idp_f = _find_baseline_pair(study, sample_name,
                                                    group_prefix, inp)
                if ids_f and idp_f:
                    try:
                        ex_idp, ex_ids, ex_idt, ex_n = _read_existing_nums(
                            ids_f, idp_f, blocks, center,
                            sample_name, group_prefix, digits,
                        )
                    except ValueError as e:
                        print(f"ERROR: {e}")
                        return False
                    entry.update(mode="extend",
                                 existing_n=ex_n,
                                 ex_idp=ex_idp, ex_ids=ex_ids, ex_idt=ex_idt,
                                 old_ids_file=ids_f, old_idp_file=idp_f)
                    used_idp.update(ex_idp)
                    used_ids.update(ex_ids)
                    used_idt.update(ex_idt)
                else:
                    entry["mode"] = "new"
            else:
                entry["mode"] = "new"

            plan.append(entry)

    # ── Validate total new IDs against pool limits ────────────────────────────
    total_new = sum(e["add_n"] for e in plan)
    max_possible = (10 ** digits - 10 ** (digits - 1) - 3) // 3
    if digits == 10:
        max_possible = 2_147_483_647
    if total_new > max_possible:
        print(f"ERROR: {total_new} new IDs requested but max for {digits} digits is {max_possible}.")
        return False

    # ── Print plan ────────────────────────────────────────────────────────────
    mode_label = "extend" if extend_mode else "new (all fresh)"
    print(f"\nMode: {mode_label}")
    print(f"\n{'Sample':<20} {'Group':>6} {'Action':<8} {'Add':>6} {'Existing':>9}")
    print("-" * 55)
    for e in plan:
        existing_str = str(e.get("existing_n", "—")).rjust(9)
        print(f"  {e['sample_name']:<18} {e['group_prefix']:>6} "
              f"{e['mode']:<8} {e['add_n']:>6} {existing_str}")
    print("-" * 55)
    print(f"  New IDs to generate: {total_new}")
    print()
    print(f"ID-P pool : {lo_idp} – {hi_idp}")
    print(f"ID-S pool : {lo_ids} – {hi_ids}")
    print(f"ID-T pool : {lo_idt} – {hi_idt}")
    print(f"Case prefix: '{case_prefix}'   Control prefix: '{control_prefix}'\n")

    # ── Draw all NEW random numbers globally once ─────────────────────────────
    # used_* already contains all existing numbers, so new draws cannot collide.
    new_idp_pool = _unique_randoms(lo_idp, hi_idp, total_new, used_idp)
    new_ids_pool = _unique_randoms(lo_ids, hi_ids, total_new, used_ids)
    new_idt_pool = _unique_randoms(lo_idt, hi_idt, total_new, used_idt)

    ts = timestamp()
    pos = 0

    for e in plan:
        sample_name  = e["sample_name"]
        group_prefix = e["group_prefix"]
        group_label  = e["group_label"]
        add_n        = e["add_n"]
        mode         = e["mode"]

        new_idp = new_idp_pool[pos:pos + add_n]
        new_ids = new_ids_pool[pos:pos + add_n]
        new_idt = new_idt_pool[pos:pos + add_n]
        pos += add_n

        if mode == "extend":
            all_idp = e["ex_idp"] + new_idp
            all_ids = e["ex_ids"] + new_ids
            all_idt = e["ex_idt"] + new_idt
            total_n = e["existing_n"] + add_n
            # Rename old files before writing new ones
            e["old_ids_file"].rename(e["old_ids_file"].with_suffix(".old"))
            e["old_idp_file"].rename(e["old_idp_file"].with_suffix(".old"))
            action_str = f"extended {e['existing_n']} → {total_n}"
        else:
            all_idp, all_ids, all_idt = new_idp, new_ids, new_idt
            total_n = add_n
            action_str = f"{add_n} new"

        idp_file, ids_file = _write_baseline_for_track(
            study, center, sample_name, group_prefix,
            total_n, all_idp, all_ids, all_idt,
            blocks, checksum_fn, out, ts,
            shuffle=shuffle,
        )
        print(f"  [{sample_name} / {group_prefix}] {group_label}: {action_str}")
        print(f"    IDP→IDT : {idp_file.name}")
        if ids_file:
            print(f"    IDS→IDT : {ids_file.name}")
        if mode == "extend":
            print(f"    (old files renamed to .old)")

    print("\nDone.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# F2. GENERATE FOLLOW-UPs
# ─────────────────────────────────────────────────────────────────────────────

def generate_followups(study, center, digits, blocks, checksum_name, visit,
                       input_dir, output_dir):
    """
    Generate follow-up IDs from existing IDS_IDT baseline files (including batch-generated ones).
    """
    checksum_fn = CHECKSUMS[checksum_name]
    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    baseline_files = sorted(inp.glob(f"*{study}_IDS_IDT_*_Baseline.txt"))
    if not baseline_files:
        print(f"ERROR: No baseline files found for study '{study}' in {inp}")
        return False

    ts = timestamp()

    for bf in baseline_files:
        track_name = get_param_from_filename(str(bf), "T")
        group      = get_param_from_filename(str(bf), "G")   # "" if not a batch file

        with open(bf, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            if header != ["IDS", "IDS128", "IDT"]:
                print(f"ERROR: Unexpected header in {bf.name}: {header}")
                return False
            rows = [r for r in reader if r]

        len_c = len(center)
        len_t = len(track_name)
        len_g = len(group)
        pos_n = field_start(blocks, "N", len_c, len_t, digits, group_len=len_g)

        ids_out  = []
        idsv_out = []

        for row in rows:
            ids_id = row[0]
            n = int(ids_id[pos_n:pos_n + digits]) if pos_n >= 0 else 0
            ids_rebuilt = build_id(blocks, center, track_name, n, 1,     checksum_fn, group=group)
            idsv_new    = build_id(blocks, center, track_name, n, visit,  checksum_fn, group=group)
            ids_out.append((ids_rebuilt,  format_code128(ids_rebuilt)))
            idsv_out.append((idsv_new,    format_code128(idsv_new)))

        track_n = len(rows)
        g_tag   = f"_G={group}" if group else ""
        out_file = out / f"{ts}_{study}_IDS_IDSV{visit}_T={track_name}{g_tag}_N={track_n}_V={visit}.txt"
        _write_tsv(out_file,
                   ["IDS", f"IDSV{visit}", "IDS128", f"IDSV{visit}128"],
                   ((ids, idsv, ids128, idsv128)
                    for (ids, ids128), (idsv, idsv128) in zip(ids_out, idsv_out)))

        label = f"{track_name}/{group}" if group else track_name
        print(f"  [{label}] {track_n} follow-ups (V={visit})  →  {out_file.name}")

    print("Done.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# F3. ADD NEW EMPTY TRACK
# ─────────────────────────────────────────────────────────────────────────────

def add_track(study, track_name, output_dir, shuffle=False):
    """Create empty IDP_IDT (and optionally IDS_IDT) baseline files for a new track (N=0)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = timestamp()

    kinds = [("IDP_IDT", ["IDP", "IDP128", "IDT"])]
    if shuffle:
        kinds.append(("IDS_IDT", ["IDS", "IDS128", "IDT"]))
    for kind, header in kinds:
        f = out / f"{ts}_{study}_{kind}_T={track_name}_N=0_Baseline.txt"
        _write_tsv(f, header, [])
        print(f"  Created {f.name}")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# F4. EXTEND PREVIOUSLY GENERATED BASELINE
# ─────────────────────────────────────────────────────────────────────────────

def extend_baseline(study, center, tracks, new_samples, digits, blocks,
                    checksum_name, input_dir, output_dir, shuffle=False):
    """
    Add new subjects to an existing baseline.
    tracks      : list of (track_name, existing_count)
    new_samples : dict { track_name: additional_count }
    """
    checksum_fn = CHECKSUMS[checksum_name]
    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    lo_idp, hi_idp, lo_ids, hi_ids, lo_idt, hi_idt = _id_pools(digits)
    ts = timestamp()

    for track_name, existing_n in tracks:
        add_n    = new_samples.get(track_name, 0)
        total_n  = existing_n + add_n

        ids_files = sorted(inp.glob(f"*{study}_IDS_IDT_*T={track_name}*_Baseline.txt"))
        idp_files = sorted(inp.glob(f"*{study}_IDP_IDT_*T={track_name}*_Baseline.txt"))

        if not ids_files:
            print(f"ERROR: IDS baseline for track '{track_name}' not found in {inp}")
            return False
        if not idp_files:
            print(f"ERROR: IDP baseline for track '{track_name}' not found in {inp}")
            return False

        actual_ids = count_data_lines(str(ids_files[0]))
        actual_idp = count_data_lines(str(idp_files[0]))
        if actual_ids != existing_n:
            print(f"ERROR: IDS file has {actual_ids} records, declared {existing_n}")
            return False
        if actual_idp != existing_n:
            print(f"ERROR: IDP file has {actual_idp} records, declared {existing_n}")
            return False

        group  = get_param_from_filename(str(ids_files[0]), "G")
        len_c  = len(center)
        len_t  = len(track_name)
        len_g  = len(group)
        pos_n  = field_start(blocks, "N", len_c, len_t, digits, group_len=len_g)

        idt_to_ids_num = {}
        with open(ids_files[0], encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)
            for row in reader:
                if not row:
                    continue
                ids_id, _, idt_id = row[0], row[1], row[2]
                ids_n = int(ids_id[pos_n:pos_n + digits]) if pos_n >= 0 else 0
                idt_n = int(idt_id[pos_n:pos_n + digits]) if pos_n >= 0 else 0
                idt_to_ids_num[idt_n] = ids_n

        idp_nums_existing = []
        idt_nums_existing = []
        with open(idp_files[0], encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)
            for row in reader:
                if not row:
                    continue
                idp_id, _, idt_id = row[0], row[1], row[2]
                idp_nums_existing.append(int(idp_id[pos_n:pos_n + digits]) if pos_n >= 0 else 0)
                idt_nums_existing.append(int(idt_id[pos_n:pos_n + digits]) if pos_n >= 0 else 0)

        ids_nums_matched = []
        for idt_n in idt_nums_existing:
            if idt_n not in idt_to_ids_num:
                print(f"ERROR: IDT {idt_n} in IDP file has no match in IDS file.")
                return False
            ids_nums_matched.append(idt_to_ids_num[idt_n])

        new_idp = _unique_randoms(lo_idp, hi_idp, add_n, set(idp_nums_existing))
        new_ids = _unique_randoms(lo_ids, hi_ids, add_n, set(ids_nums_matched))
        new_idt = _unique_randoms(lo_idt, hi_idt, add_n, set(idt_nums_existing))

        all_idp_nums = idp_nums_existing + new_idp
        all_ids_nums = ids_nums_matched  + new_ids
        all_idt_nums = idt_nums_existing + new_idt

        idp_file, ids_file = _write_baseline_for_track(
            study, center, track_name, group,
            total_n,
            all_idp_nums, all_ids_nums, all_idt_nums,
            blocks, checksum_fn, out, ts,
            shuffle=shuffle,
        )

        ids_files[0].rename(ids_files[0].with_suffix(".old"))
        idp_files[0].rename(idp_files[0].with_suffix(".old"))
        print(f"  [{track_name}] extended {existing_n} → {total_n}")
        print(f"    IDP→IDT : {idp_file.name}")
        print(f"    IDS→IDT : {ids_file.name}")
        print(f"    (old files renamed to .old)")

    print("Done.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# F5. CREATE EXTERNAL IDs
# ─────────────────────────────────────────────────────────────────────────────

def create_external_ids(study, center, ext_project, digits, blocks, checksum_name,
                        input_dir, output_dir):
    """
    Create external IDs (IDE) linked to existing IDS via IDT.
    External IDs use digits+1 (or MAX_DIGITS) to be clearly distinguishable.
    """
    checksum_fn = CHECKSUMS[checksum_name]
    MAX_DIGITS  = 10
    ext_digits  = min(digits + 1, MAX_DIGITS)
    lo_ide = 10 ** (ext_digits - 1) + 1
    hi_ide = 10 ** ext_digits - 1

    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    baseline_files = sorted(inp.glob(f"*{study}_IDS_IDT_*_Baseline.txt"))
    if not baseline_files:
        print(f"ERROR: No baseline files found for study '{study}' in {inp}")
        return False

    ts = timestamp()

    for bf in baseline_files:
        track_name = get_param_from_filename(str(bf), "T")
        group      = get_param_from_filename(str(bf), "G")

        with open(bf, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            if header != ["IDS", "IDS128", "IDT"]:
                print(f"ERROR: Unexpected header in {bf.name}: {header}")
                return False
            rows = [r for r in reader if r]

        track_n  = len(rows)
        ide_nums = _unique_randoms(lo_ide, hi_ide, track_n, set())

        ids_ids = [row[0] for row in rows]
        ids128  = [row[1] for row in rows]
        ide_ids = [build_id(blocks, center, track_name, n, 0, checksum_fn, group=group)
                   for n in ide_nums]
        ide128  = [format_code128(x) for x in ide_ids]

        g_tag    = f"_G={group}" if group else ""
        out_file = out / f"{ts}_{study}_IDS_IDE_T={track_name}{g_tag}_N={track_n}_{ext_project}.txt"
        _write_tsv(out_file, ["IDS", "IDE", "IDS128", "IDE128"],
                   zip(ids_ids, ide_ids, ids128, ide128))

        label = f"{track_name}/{group}" if group else track_name
        print(f"  [{label}] {track_n} external IDs  →  {out_file.name}")

    print("Done.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_tracks(s: str) -> list:
    """Parse 'TrackA:100,TrackB:200' → [('TrackA', 100), ('TrackB', 200)]."""
    result = []
    for part in s.split(","):
        name, count = part.strip().split(":")
        result.append((name.strip(), int(count.strip())))
    return result


def main():
    parser = argparse.ArgumentParser(
        prog="idgenerator",
        description="Clinical study randomized ID generator (cross-platform Python port)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── shared parent ────────────────────────────────────────────────────────
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--study",    required=True)
    shared.add_argument("--center",   default="",
                        help="Study center code (default: empty)")
    shared.add_argument("--digits",   type=int, default=5,
                        help="Digits for unique number field (default: 5)")
    shared.add_argument("--blocks",   default="CTNVX",
                        help="Building block order, e.g. CTNVX or CTGNVX (default: CTNVX)")
    shared.add_argument("--checksum", default="Damm_2004",
                        choices=list(CHECKSUMS.keys()),
                        help="Checksum algorithm (default: Damm_2004)")
    shared.add_argument("--output",   default=".",
                        help="Output directory (default: current directory)")
    shared.add_argument("--shuffle", action="store_true",
                        help="Also generate the row-shuffled IDS_IDT file. "
                             "By default only the IDP_IDT file is written.")

    # ── baseline ─────────────────────────────────────────────────────────────
    p = sub.add_parser("baseline", parents=[shared],
                       help="Generate a fresh baseline for named tracks")
    p.add_argument("--tracks", required=True,
                   help="Track names and counts, e.g. 'TrackA:100,TrackB:200'")

    # ── batch ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("batch", parents=[shared],
                       help="Generate baseline from a sample sheet (cases + controls per sample)")
    p.add_argument("--input-file", required=True,
                   help="Sample sheet file (.txt .csv .tsv .xlsx .xls). "
                        "Columns: SampleName, NCases, NControls")
    p.add_argument("--case-prefix",    default="S",
                   help="Single-letter prefix for case IDs (default: S)")
    p.add_argument("--control-prefix", default="C",
                   help="Single-letter prefix for control IDs (default: C)")
    p.add_argument("--extend", action="store_true",
                   help="Extend existing baselines instead of creating new ones. "
                        "Counts in the sheet are treated as ADDITIONAL subjects to add. "
                        "Samples with no existing baseline are created fresh.")
    p.add_argument("--input-dir", default=None,
                   help="Where to look for existing baseline files when using --extend. "
                        "Defaults to --output if not specified.")

    # ── followup ─────────────────────────────────────────────────────────────
    p = sub.add_parser("followup", parents=[shared],
                       help="Generate follow-up visit IDs from existing baseline files")
    p.add_argument("--visit",     required=True, type=int,
                   help="Follow-up visit number (e.g. 2)")
    p.add_argument("--input-dir", default=".",
                   help="Directory containing baseline IDS_IDT files (default: .)")

    # ── add-track ─────────────────────────────────────────────────────────────
    p = sub.add_parser("add-track",
                       help="Create an empty baseline file pair for a new track")
    p.add_argument("--study",  required=True)
    p.add_argument("--track",  required=True, help="New track name")
    p.add_argument("--output", default=".")
    p.add_argument("--shuffle", action="store_true",
                   help="Also create the IDS_IDT placeholder file.")

    # ── extend ───────────────────────────────────────────────────────────────
    p = sub.add_parser("extend", parents=[shared],
                       help="Add new subjects to an existing baseline")
    p.add_argument("--tracks", required=True,
                   help="Existing tracks and counts, e.g. 'TrackA:100,TrackB:200'")
    p.add_argument("--new-samples", required=True,
                   help="New subjects per track, e.g. 'TrackA:20,TrackB:30'")
    p.add_argument("--input-dir", default=".",
                   help="Directory containing the existing baseline files (default: .)")

    # ── external ─────────────────────────────────────────────────────────────
    p = sub.add_parser("external", parents=[shared],
                       help="Create external-project IDs linked to an existing baseline")
    p.add_argument("--ext-project", required=True,
                   help="External project name (used in filenames)")
    p.add_argument("--input-dir", default=".")

    args = parser.parse_args()

    if args.command == "baseline":
        ok = generate_baseline(args.study, args.center, _parse_tracks(args.tracks),
                               args.digits, args.blocks, args.checksum, args.output,
                               shuffle=args.shuffle)

    elif args.command == "batch":
        ok = generate_batch(args.study, args.center, args.input_file,
                            args.digits, args.blocks, args.checksum,
                            args.case_prefix, args.control_prefix, args.output,
                            extend_mode=args.extend,
                            input_dir=args.input_dir,
                            shuffle=args.shuffle)

    elif args.command == "followup":
        ok = generate_followups(args.study, args.center,
                                args.digits, args.blocks, args.checksum,
                                args.visit, args.input_dir, args.output)

    elif args.command == "add-track":
        ok = add_track(args.study, args.track, args.output, shuffle=args.shuffle)

    elif args.command == "extend":
        tracks      = _parse_tracks(args.tracks)
        new_samples = dict(_parse_tracks(args.new_samples))
        ok = extend_baseline(args.study, args.center, tracks, new_samples,
                             args.digits, args.blocks, args.checksum,
                             args.input_dir, args.output, shuffle=args.shuffle)

    elif args.command == "external":
        ok = create_external_ids(args.study, args.center, args.ext_project,
                                 args.digits, args.blocks, args.checksum,
                                 args.input_dir, args.output)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
