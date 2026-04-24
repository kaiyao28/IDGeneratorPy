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
      --digits 5 --blocks CRGNVX --checksum Damm_2004 \\
      --output ./output

# Batch-generate baseline from a sample sheet (cases & controls per sample):
  python idgenerator.py batch \\
      --study MyStudy --center 01 \\
      --input-file samples.xlsx \\
      --digits 5 --blocks CRGNVX --checksum Damm_2004 \\
      --case-prefix S --control-prefix C \\
      --output ./output

  Input file columns (txt/csv/tsv/xlsx/xls):
    SampleName   NCases   NControls
    Sample001    100      200
    Sample002    50       75

  Output files produced per sample (in per_site/ subfolder):
    {date}_{study}_IDP_IDT_T={sample}_G=S_N={cases}_First.txt    (first creation — tab-separated, has barcode cols)
    {date}_{study}_IDS_IDT_T={sample}_G=S_N={cases}_First.txt
    {date}_{study}_IDP_IDT_T={sample}_G=C_N={controls}_First.txt
    {date}_{study}_IDS_IDT_T={sample}_G=C_N={controls}_First.txt
    (re-runs that extend existing files produce _Updated.txt instead)

# Generate follow-up visit 2 from baseline files:
  python idgenerator.py followup \\
      --study MyStudy --center 01 \\
      --digits 5 --blocks CRGNVX --checksum Damm_2004 \\
      --visit 2 --input-dir ./output --output ./output

# Add a new empty track placeholder:
  python idgenerator.py add-track \\
      --study MyStudy --track TrackC --output ./output

# Extend existing baseline with new subjects:
  python idgenerator.py extend \\
      --study MyStudy --center 01 \\
      --tracks "TrackA:100,TrackB:200" \\
      --new-samples "TrackA:20,TrackB:30" \\
      --digits 5 --blocks CRGNVX --checksum Damm_2004 \\
      --input-dir ./output --output ./output

# Create external IDs linked to an existing baseline:
  python idgenerator.py external \\
      --study MyStudy --center 01 --ext-project ExtProj \\
      --digits 5 --blocks CRGNVX --checksum Damm_2004 \\
      --input-dir ./output --output ./output

Building blocks (--blocks):
  S = Study name prefix (--study value embedded in every ID)
  C = Study center code
  R = Recruitment site name (SampleName from input sheet; multi-track batch only)
  T = Data-track abbreviation (first char of --tracks name, e.g. 'G'=Genetics)
      In standard batch mode T holds the full SampleName (site name).
  G = Group (case prefix vs control prefix — use with standard 'batch' command)
  N = Unique random number
  V = ID-type flag  (IDP=0, IDS/IDT=1)
  X = Check digit

  Recommended for standard batch (case/control): CTGNVX
  Recommended for multi-track batch:             CRTNVX  (R=site, T=track)
  Prefix any string with S to embed the study name: SCRTNVX

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

Output files:
  {date}_{study}_IDP_IDT_T={track}_N={n}_First.txt   — IDP/IDT pairs, tab-separated (barcode cols)
  {date}_{study}_IDP_IDT_T={track}_N={n}_Updated.txt
  {date}_{study}_IDS_IDT_T={track}_N={n}_First.txt   — IDS/IDT pairs, tab-separated (barcode cols)
  {date}_{study}_IDP_IDT_ALL_N={n}.txt                  — master IDP combined across all sites (with No. counter)
  {date}_{study}_IDS_IDT_ALL_N={n}.txt                  — master IDS combined across all sites (with No. counter)
"""

import argparse
import csv
import json
import random
import sys
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# STUDY CONFIG  (mirrors original Config.xml — saved once, loaded on every run)
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_FILENAME = "study.cfg"

_CONFIG_KEYS = ("study", "center", "digits", "blocks", "checksum",
                "case_prefix", "control_prefix", "output", "visit")


def _save_config(cfg: dict, output_dir: str) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / CONFIG_FILENAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"Study config saved to {path}")


def _load_config(output_dir: str) -> dict:
    """Return config dict from study.cfg in output_dir, or empty dict if not found."""
    path = Path(output_dir) / CONFIG_FILENAME
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _apply_config(args: argparse.Namespace, cfg: dict) -> None:
    """Fill in any args not supplied on the CLI from the saved config."""
    for key in _CONFIG_KEYS:
        if key in cfg and getattr(args, key, None) in (None, argparse.SUPPRESS):
            setattr(args, key, cfg[key])

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING  (mirrors original WriteInfo → LogFile.txt behaviour)
# ─────────────────────────────────────────────────────────────────────────────

_log_fh = None


def _log_init(output_dir: str) -> None:
    global _log_fh
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _log_fh = open(out / "LogFile.txt", "a", encoding="utf-8")


def _log(msg: str = "") -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {msg}" if msg else ""
    print(line)
    if _log_fh:
        _log_fh.write(line + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CHECKSUM ALGORITHMS
# ─────────────────────────────────────────────────────────────────────────────

def _id_to_numstr(id_str: str) -> str:
    """Strip [CHECKSUM], replace non-digits with ASCII codes — for checksum input."""
    s = id_str.replace("[CHECKSUM]", "")
    return "".join(ch if ch.isdigit() else str(ord(ch)) for ch in s)


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
             checksum_fn, *, group: str = "", study: str = "",
             site: str = "") -> str:
    """
    Assemble an ID string from building blocks and compute its check digit.
    G block requires `group` kwarg.  S block requires `study` kwarg.
    R block requires `site` kwarg (recruitment site name).
    """
    parts = []
    for bb in blocks:
        if   bb == "C": parts.append(center)
        elif bb == "R": parts.append(site)
        elif bb == "T": parts.append(track)
        elif bb == "G": parts.append(group)
        elif bb == "S": parts.append(study)
        elif bb == "N": parts.append(str(number))
        elif bb == "V": parts.append(str(visit))
        elif bb == "X": parts.append("[CHECKSUM]")
    raw = "".join(parts)
    return raw.replace("[CHECKSUM]", str(checksum_fn(raw)))


def field_start(blocks: str, field: str, center_len: int, track_len: int,
                digits: int, group_len: int = 0, study_len: int = 0,
                site_len: int = 0) -> int:
    """Return the 0-based character position where `field` starts inside a built ID."""
    pos = 0
    for bb in blocks:
        if bb == field:
            return pos
        if   bb == "C": pos += center_len
        elif bb == "R": pos += site_len
        elif bb == "T": pos += track_len
        elif bb == "G": pos += group_len
        elif bb == "S": pos += study_len
        elif bb == "N": pos += digits
        elif bb in ("V", "X"): pos += 1
    return -1


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────

def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d")


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
        next(f, None)  # skip header
        return sum(1 for ln in f if ln.strip())


def _unique_randoms(lo: int, hi: int, count: int, excluded: set) -> list:
    """Draw `count` unique random integers from [lo, hi] avoiding `excluded`."""
    available = hi - lo + 1 - len(excluded)
    if count > available:
        raise ValueError(
            f"Cannot draw {count} unique values: only {available} available in [{lo}, {hi}]."
        )
    # For dense draws (>10% of available pool), enumerate candidates and sample directly
    # to avoid exponentially increasing rejection retries near the pool limit.
    if count > available * 0.1:
        candidates = [x for x in range(lo, hi + 1) if x not in excluded]
        return random.sample(candidates, count)
    result = []
    used = set(excluded)
    for _ in range(count):
        n = random.randint(lo, hi)
        while n in used:
            n = random.randint(lo, hi)
        used.add(n)
        result.append(n)
    return result


def _max_pool_size(digits: int) -> int:
    """Maximum number of IDs that can be generated for a given digit count (one pool's share)."""
    if digits == 10:
        return 2_147_483_647
    return (10 ** digits - 10 ** (digits - 1) - 3) // 3


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
        f.write("\t".join(str(x) for x in header) + "\n")
        for row in rows:
            f.write("\t".join(str(x) for x in row) + "\n")


def _write_csv(path, header, rows):
    _write_tsv(path, header, rows)


def _write_numbered(path, header, rows):
    """Tab-separated with a leading No. column (1-indexed). For master ALL files."""
    rows_list = list(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(["No."] + [str(x) for x in header]) + "\n")
        for i, row in enumerate(rows_list, 1):
            f.write("\t".join([str(i)] + [str(x) for x in row]) + "\n")


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

    Supported formats: .txt  .txt  .txt  (tab or comma separated)
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
            _log(f"  Warning: skipping row {i} — non-numeric counts: {row}")
            continue
        if n_cases < 0 or n_ctrl < 0:
            _log(f"  Warning: skipping row {i} — negative counts: {row}")
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
                "Or save your file as .txt / .txt and use that instead."
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
                "Or save your file as .txt / .txt and use that instead."
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

def _build_ids_for_track(blocks, center, track_name, group, idp_nums, ids_nums, idt_nums,
                          checksum_fn, *, shuffle=False, study: str = ""):
    """
    Build ID strings for one track/group.
    Returns (idp_ids, ids_ids, idt_ids, idp128, ids128, order).
    IDS IDs are always built; order is shuffled only when shuffle=True.
    """
    # site=track_name so R block works in standard batch (where site = sample name)
    kw = dict(group=group, study=study, site=track_name)
    idp_ids = [build_id(blocks, center, track_name, n, 0, checksum_fn, **kw) for n in idp_nums]
    idt_ids = [build_id(blocks, center, track_name, n, 1, checksum_fn, **kw) for n in idt_nums]
    idp128  = [format_code128(x) for x in idp_ids]
    ids_ids = [build_id(blocks, center, track_name, n, 1, checksum_fn, **kw) for n in ids_nums]
    ids128  = [format_code128(x) for x in ids_ids]
    order   = list(range(len(idp_ids)))
    if shuffle:
        random.shuffle(order)
    return idp_ids, ids_ids, idt_ids, idp128, ids128, order


def _write_baseline_for_track(study, center, track_name, group, track_n,
                               idp_nums, ids_nums, idt_nums,
                               blocks, checksum_fn, out, ts, *,
                               shuffle=False, suffix="First"):
    """
    Build and write per-track output files.
    Returns (idp_filepath, ids_filepath, idp_rows, ids_rows).
    suffix="First" for initial creation, "Updated" when adding to existing.
    IDS rows are always returned; --shuffle controls row order only.
    """
    idp_ids, ids_ids, idt_ids, idp128, ids128, order = _build_ids_for_track(
        blocks, center, track_name, group, idp_nums, ids_nums, idt_nums,
        checksum_fn, shuffle=shuffle, study=study)

    g_tag = f"_G={group}" if group else ""

    idp_file = out / f"{ts}_{study}_IDP_IDT_T={track_name}{g_tag}_N={track_n}_{suffix}.txt"
    _write_tsv(idp_file, ["IDP", "IDP128", "IDT"], zip(idp_ids, idp128, idt_ids))
    idp_rows = list(zip(idp_ids, idp128, idt_ids,
                        [track_name] * track_n, [group] * track_n))

    ids_file = out / f"{ts}_{study}_IDS_IDT_T={track_name}{g_tag}_N={track_n}_{suffix}.txt"
    _write_tsv(ids_file, ["IDS", "IDS128", "IDT"],
               ((ids_ids[i], ids128[i], idt_ids[i]) for i in order))
    ids_rows = [(ids_ids[i], ids128[i], idt_ids[i], track_name, group) for i in order]

    return idp_file, ids_file, idp_rows, ids_rows


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
    max_possible = _max_pool_size(digits)
    if total_n > max_possible:
        _log(f"ERROR: {total_n} IDs requested but maximum for {digits} digits is {max_possible}.")
        return False

    lo_idp, hi_idp, lo_ids, hi_ids, lo_idt, hi_idt = _id_pools(digits)
    _log(f"ID-P pool : {lo_idp} – {hi_idp}")
    _log(f"ID-S pool : {lo_ids} – {hi_ids}")
    _log(f"ID-T pool : {lo_idt} – {hi_idt}")
    _log(f"Generating {total_n} IDs across {len(tracks)} track(s)…")

    idp_nums = _unique_randoms(lo_idp, hi_idp, total_n, set())
    ids_nums = _unique_randoms(lo_ids, hi_ids, total_n, set())
    idt_nums = _unique_randoms(lo_idt, hi_idt, total_n, set())

    ts = timestamp()
    pos = 0
    all_idp_rows, all_ids_rows = [], []
    for track_name, track_n in tracks:
        idp_file, ids_file, idp_rows, ids_rows = _write_baseline_for_track(
            study, center, track_name, "",
            track_n,
            idp_nums[pos:pos + track_n],
            ids_nums[pos:pos + track_n],
            idt_nums[pos:pos + track_n],
            blocks, checksum_fn, out, ts,
            shuffle=shuffle, suffix="First",
        )
        all_idp_rows.extend(idp_rows)
        all_ids_rows.extend(ids_rows)
        _log(f"  [{track_name}] {track_n} IDs  →  {idp_file.name}")
        _log(f"                         {ids_file.name}")
        pos += track_n

    # ALL files: no barcode columns — clean IDs only, safe for Excel/R merging
    combined_idp = out / f"{ts}_{study}_IDP_IDT_ALL_N={total_n}.txt"
    _write_numbered(combined_idp, ["IDP", "IDT", "Track", "Group"],
                    [(r[0], r[2], r[3], r[4]) for r in all_idp_rows])
    _log(f"  Combined IDP : {combined_idp.name}")
    if all_ids_rows:
        combined_ids = out / f"{ts}_{study}_IDS_IDT_ALL_N={total_n}.txt"
        _write_numbered(combined_ids, ["IDS", "IDT", "Track", "Group"],
                        [(r[0], r[2], r[3], r[4]) for r in all_ids_rows])
        _log(f"  Combined IDS : {combined_ids.name}")

    _log("Done.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# F1b. MULTI-TRACK BASELINE  (one row per participant, one column per track)
# ─────────────────────────────────────────────────────────────────────────────

def generate_multitrack_baseline(study, center, track_names, sample_count,
                                  digits, blocks, checksum_name, output_dir):
    """
    Generate IDs for N participants across multiple data tracks.

    Every participant receives one IDT (linkage key) and one IDP per track.
    All tracks share the same N — if a participant is missing data for one
    track they still hold an ID for it.

    Output columns: IDT | IDP_Track1 | IDP_Track2 | ...
    One row per participant, one file. No IDS needed for anonymised cohorts.
    """
    checksum_fn = CHECKSUMS[checksum_name]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    total_idp = sample_count * len(track_names)
    max_possible = _max_pool_size(digits)
    if total_idp > max_possible:
        _log(f"ERROR: {total_idp} IDP draws needed ({sample_count} × {len(track_names)} tracks); "
             f"max for {digits} digits is {max_possible}.")
        return False

    lo_idp, hi_idp, _, _, lo_idt, hi_idt = _id_pools(digits)
    _log(f"Tracks       : {', '.join(track_names)}")
    _log(f"Participants : {sample_count}")
    _log(f"ID-P pool    : {lo_idp} – {hi_idp}")
    _log(f"ID-T pool    : {lo_idt} – {hi_idt}")

    idt_nums = _unique_randoms(lo_idt, hi_idt, sample_count, set())
    idt_ids  = [build_id(blocks, center, "", n, 1, checksum_fn, study=study) for n in idt_nums]

    used_idp = set()
    idp_by_track = {}
    for t in track_names:
        nums = _unique_randoms(lo_idp, hi_idp, sample_count, used_idp)
        used_idp.update(nums)
        idp_by_track[t] = [build_id(blocks, center, t, n, 0, checksum_fn, study=study) for n in nums]

    ts = timestamp()
    track_tag = "+".join(track_names)
    out_file = out / f"{ts}_{study}_IDP_T={track_tag}_N={sample_count}_First.txt"
    header = ["IDT"] + [f"IDP_{t}" for t in track_names]
    rows   = [[idt_ids[i]] + [idp_by_track[t][i] for t in track_names]
              for i in range(sample_count)]
    _write_csv(out_file, header, rows)
    _log(f"  Written : {out_file.name}")
    _log("Done.")
    return True


def extend_multitrack_baseline(study, center, add_n, digits, blocks, checksum_name,
                                input_dir, output_dir):
    """
    Extend a multi-track baseline with add_n new participants.
    Track names and existing N are read from the existing file automatically.
    All tracks are extended by the same count.
    """
    checksum_fn = CHECKSUMS[checksum_name]
    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        f for sfx in ("First", "Updated")
        for f in inp.glob(f"*{study}_IDP_T=*_{sfx}.txt")
        if "+" in f.stem
    )
    if not candidates:
        _log(f"ERROR: No multi-track baseline found for study '{study}' in {inp}")
        return False
    existing_file = candidates[-1]

    with open(existing_file, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        existing_rows = [r for r in reader if r]

    track_names = [h[4:] for h in header if h.startswith("IDP_")]
    existing_n  = len(existing_rows)
    total_n     = existing_n + add_n

    _log(f"File         : {existing_file.name}")
    _log(f"Tracks       : {', '.join(track_names)}")
    _log(f"Extending    : {existing_n} → {total_n}")

    lo_idp, hi_idp, _, _, lo_idt, hi_idt = _id_pools(digits)

    # Extract existing numbers to avoid collisions
    s_len = len(study)
    pos_idt = field_start(blocks, "N", len(center), 0, digits, study_len=s_len)
    used_idt = set()
    used_idp = set()
    for row in existing_rows:
        if pos_idt >= 0:
            used_idt.add(int(row[0][pos_idt:pos_idt + digits]))
        for i, t in enumerate(track_names):
            pos_idp = field_start(blocks, "N", len(center), len(t), digits, study_len=s_len)
            if pos_idp >= 0:
                used_idp.add(int(row[i + 1][pos_idp:pos_idp + digits]))

    new_idt_nums = _unique_randoms(lo_idt, hi_idt, add_n, used_idt)
    new_idt_ids  = [build_id(blocks, center, "", n, 1, checksum_fn, study=study) for n in new_idt_nums]

    new_used = set(used_idp)
    new_idp_by_track = {}
    for t in track_names:
        nums = _unique_randoms(lo_idp, hi_idp, add_n, new_used)
        new_used.update(nums)
        new_idp_by_track[t] = [build_id(blocks, center, t, n, 0, checksum_fn, study=study) for n in nums]

    new_rows = [[new_idt_ids[i]] + [new_idp_by_track[t][i] for t in track_names]
                for i in range(add_n)]
    all_rows = existing_rows + new_rows

    ts = timestamp()
    track_tag = "+".join(track_names)
    new_file = out / f"{ts}_{study}_IDP_T={track_tag}_N={total_n}_Updated.txt"
    _write_csv(new_file, header, all_rows)
    existing_file.rename(existing_file.with_suffix(".old"))
    _log(f"  Written : {new_file.name}")
    _log("Done.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# BATCH BASELINE  (sample sheet with cases + controls)
# ─────────────────────────────────────────────────────────────────────────────

def _read_existing_nums(ids_file, idp_file: Path, blocks: str,
                        center: str, track_name: str, group: str, digits: int,
                        study_len: int = 0):
    """
    Read the numeric N-field values from an existing IDP_IDT baseline file.
    ids_file may be None when the original run did not use --shuffle.
    Returns (idp_nums, ids_nums_matched, idt_nums, existing_count).
    IDS numbers are cross-referenced via IDT when the IDS file is present;
    otherwise an empty list is returned (those numbers were never written out).
    """
    len_c = len(center)
    len_t = len(track_name)
    len_g = len(group)
    pos_n = field_start(blocks, "N", len_c, len_t, digits, group_len=len_g, study_len=study_len,
                        site_len=len_t)

    # IDS file: build idt_num → ids_num lookup (only if the file exists)
    idt_to_ids = {}
    if ids_file is not None:
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
    if idt_to_ids:
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
    Return (ids_file_or_None, idp_file) for an existing baseline, or (None, None) if not found.
    IDP_IDT is always present; IDS_IDT only exists when --shuffle was used originally.
    Searches both search_dir and search_dir/per_site/ (where batch always writes individual files).
    Matches the most recent file when multiple timestamps exist.
    """
    g_tag = f"_G={group}" if group else ""
    candidate_dirs = [search_dir, search_dir / "per_site"]
    idp_matches, ids_matches = [], []
    for d in candidate_dirs:
        if d.exists():
            for sfx in ("First", "Updated"):
                idp_matches += list(d.glob(f"*{study}_IDP_IDT_T={sample_name}{g_tag}_*_{sfx}.txt"))
                ids_matches += list(d.glob(f"*{study}_IDS_IDT_T={sample_name}{g_tag}_*_{sfx}.txt"))
    idp_matches.sort()
    ids_matches.sort()
    if not idp_matches:
        return None, None
    return (ids_matches[-1] if ids_matches else None), idp_matches[-1]


def _rebuild_master_all(study: str, out: Path, ts: str):
    """
    Rebuild the master IDP_IDT_ALL and IDS_IDT_ALL files by reading every current
    (non-.old) per-site file in per_site/. Called after each batch run so the master
    files always reflect the complete state of ALL sites across ALL waves.
    Old master ALL files are renamed to .old.
    """
    per_site = out / "per_site"

    idp_files = sorted(f for f in per_site.glob(f"*{study}_IDP_IDT_T=*.txt"))
    ids_files = sorted(f for f in per_site.glob(f"*{study}_IDS_IDT_T=*.txt"))

    # ALL files: IDP/IDS and IDT only — no barcode columns, safe for Excel/R merging
    all_idp_rows, all_ids_rows = [], []
    for f in idp_files:
        track = get_param_from_filename(str(f), "T")
        group = get_param_from_filename(str(f), "G")
        with open(f, encoding="utf-8") as fh:
            rdr = csv.reader(fh, delimiter="\t")
            next(rdr)
            for cols in rdr:
                if cols:
                    all_idp_rows.append([cols[0], cols[2], track, group])  # IDP, IDT

    for f in ids_files:
        track = get_param_from_filename(str(f), "T")
        group = get_param_from_filename(str(f), "G")
        with open(f, encoding="utf-8") as fh:
            rdr = csv.reader(fh, delimiter="\t")
            next(rdr)
            for cols in rdr:
                if cols:
                    all_ids_rows.append([cols[0], cols[2], track, group])  # IDS, IDT

    # Retire old master ALL files
    for old in sorted(out.glob(f"*_{study}_IDP_IDT_ALL_*.txt")):
        old.rename(old.with_suffix(".old"))
    for old in sorted(out.glob(f"*_{study}_IDS_IDT_ALL_*.txt")):
        old.rename(old.with_suffix(".old"))

    master_idp = out / f"{ts}_{study}_IDP_IDT_ALL_N={len(all_idp_rows)}.txt"
    _write_numbered(master_idp, ["IDP", "IDT", "Track", "Group"], all_idp_rows)

    master_ids = out / f"{ts}_{study}_IDS_IDT_ALL_N={len(all_ids_rows)}.txt"
    _write_numbered(master_ids, ["IDS", "IDT", "Track", "Group"], all_ids_rows)

    return master_idp, master_ids


def _find_multitrack_site_file(study: str, site_name: str, track_tag: str,
                               search_dir: Path, id_type: str = "IDP"):
    """Return the most recent per-site multi-track file, or None if not found."""
    candidates = []
    for d in [search_dir, search_dir / "per_site"]:
        if d.exists():
            for sfx in ("First", "Updated"):
                if track_tag:
                    candidates += list(d.glob(
                        f"*{study}_{id_type}_T={track_tag}_SITE={site_name}_*_{sfx}.txt"))
                else:
                    candidates += list(d.glob(
                        f"*{study}_{id_type}_IDT_SITE={site_name}_*_{sfx}.txt"))
    candidates.sort()
    return candidates[-1] if candidates else None


def generate_batch(study, center, input_file, digits, blocks, checksum_name,
                   case_prefix, control_prefix, output_dir,
                   extend_mode=False, input_dir=None, shuffle=False, samples=None):
    """
    Read a sample sheet and generate one baseline per sample×group.

    Output layout
    -------------
    output_dir/                    ← main directory (logs + config + combined files only)
      IDP_IDT_ALL_*.txt            ← all sites/groups merged, with No., Track and Group columns
      IDS_IDT_ALL_*.txt            ← same for study data (row order shuffled across all sites)
      LogFile.txt
      study.cfg
    output_dir/per_site/           ← one file per site×group (always written here)
      IDP_IDT_T=…_G=…_*.txt        ← tab-separated, contains barcode columns
      IDS_IDT_T=…_G=…_*.txt       ← only when --shuffle is used

    Extend mode (default — auto-detected per row)
    ----------------------------------------------
    If an existing baseline is found in per_site/ for a sample+group, those IDs are
    preserved and new IDs are appended (old file renamed to .old).
    If no existing baseline is found, a fresh file is created.
    Use --fresh to force all rows to be treated as new regardless.
    """
    checksum_fn = CHECKSUMS[checksum_name]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    inp = Path(input_dir) if input_dir else out

    if samples is None:
        _log(f"Reading sample sheet: {input_file}")
        try:
            samples = read_sample_sheet(input_file)
        except (ValueError, ImportError) as e:
            _log(f"ERROR: {e}")
            return False
        if not samples:
            _log("ERROR: No valid samples found in input file.")
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
                if idp_f:
                    try:
                        ex_idp, ex_ids, ex_idt, ex_n = _read_existing_nums(
                            ids_f, idp_f, blocks, center,
                            sample_name, group_prefix, digits,
                            study_len=len(study),
                        )
                    except ValueError as e:
                        _log(f"ERROR: {e}")
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
    max_possible = _max_pool_size(digits)
    if total_new > max_possible:
        _log(f"ERROR: {total_new} new IDs requested but max for {digits} digits is {max_possible}.")
        return False

    # ── Print plan ────────────────────────────────────────────────────────────
    mode_label = "extend" if extend_mode else "new (all fresh)"
    _log(f"\nMode: {mode_label}")
    _log(f"\n{'Sample':<20} {'Group':>6} {'Action':<8} {'Add':>6} {'Existing':>9}")
    _log("-" * 55)
    for e in plan:
        existing_str = str(e.get("existing_n", "—")).rjust(9)
        _log(f"  {e['sample_name']:<18} {e['group_prefix']:>6} "
              f"{e['mode']:<8} {e['add_n']:>6} {existing_str}")
    _log("-" * 55)
    _log(f"  New IDs to generate: {total_new}")
    _log()
    _log(f"ID-P pool : {lo_idp} – {hi_idp}")
    _log(f"ID-S pool : {lo_ids} – {hi_ids}")
    _log(f"ID-T pool : {lo_idt} – {hi_idt}")
    _log(f"Case prefix: '{case_prefix}'   Control prefix: '{control_prefix}'\n")

    # ── Draw all NEW random numbers globally once ─────────────────────────────
    # used_* already contains all existing numbers, so new draws cannot collide.
    # IDS pool may need extra draws for extend entries whose original run had no --shuffle
    # (ex_ids was empty, so those existing records never had IDS IDs assigned).
    ids_backfill = sum(e.get("existing_n", 0) for e in plan
                       if e["mode"] == "extend" and not e.get("ex_ids"))
    new_idp_pool = _unique_randoms(lo_idp, hi_idp, total_new, used_idp)
    new_ids_pool = _unique_randoms(lo_ids, hi_ids, total_new + ids_backfill, used_ids)
    new_idt_pool = _unique_randoms(lo_idt, hi_idt, total_new, used_idt)
    ids_backfill_pos = total_new  # backfill draws start after the regular new-IDs slice

    ts = timestamp()
    pos = 0

    # Individual per-site files always written to per_site/ subfolder
    per_site_out = out / "per_site"
    per_site_out.mkdir(parents=True, exist_ok=True)

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
            existing_n = e["existing_n"]
            ex_ids = e["ex_ids"]
            if not ex_ids:
                # Original run had no IDS file; backfill IDS IDs for existing records
                bf_ids = new_ids_pool[ids_backfill_pos:ids_backfill_pos + existing_n]
                ids_backfill_pos += existing_n
                all_ids = bf_ids + new_ids
            else:
                all_ids = ex_ids + new_ids
            all_idp = e["ex_idp"] + new_idp
            all_idt = e["ex_idt"] + new_idt
            total_n = existing_n + add_n
            if e["old_ids_file"]:
                e["old_ids_file"].rename(e["old_ids_file"].with_suffix(".old"))
            e["old_idp_file"].rename(e["old_idp_file"].with_suffix(".old"))
            action_str = f"extended {existing_n} → {total_n}"
        else:
            all_idp, all_ids, all_idt = new_idp, new_ids, new_idt
            total_n = add_n
            action_str = f"{add_n} new"
        e["total_n"] = total_n

        _write_baseline_for_track(
            study, center, sample_name, group_prefix,
            total_n, all_idp, all_ids, all_idt,
            blocks, checksum_fn, per_site_out, ts,
            shuffle=shuffle,
            suffix="Updated" if mode == "extend" else "First",
        )
        _log(f"  [{sample_name} / {group_prefix}] {group_label}: {action_str}")
        if mode == "extend":
            _log(f"    (old files renamed to .old)")

    # Rebuild master ALL files from every current per-site file (all waves, all sites)
    master_idp, master_ids = _rebuild_master_all(study, out, ts)
    _log(f"  Master IDP_ALL : {master_idp.name}")
    _log(f"  Master IDS_ALL : {master_ids.name}")

    _log("\nDone.")
    return True


def _generate_batch_multitrack(study, center, samples, track_names, digits, blocks,
                               checksum_name, output_dir, input_dir=None, anon=False,
                               case_prefix="S", control_prefix="C"):
    """
    Batch-generate multi-track IDs from a sample sheet.

    samples    : list of (site_name, n_cases, n_controls) — totals are summed per site
    track_names: list of track name strings e.g. ['Genetics', 'Phenotype'], or [] for single IDS
    anon       : True  → draw from IDS pool, label columns IDS_* (anonymised cohort)
                 False → draw from IDP pool, label columns IDP_*

    G block behaviour:
      - If G is in --blocks, cases and controls get their respective prefix in every ID,
        whether in single-IDS or multi-track mode.
      - If G is absent, all participants are built with group="" (no prefix).
    """
    has_tracks = bool(track_names)

    checksum_fn = CHECKSUMS[checksum_name]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    inp = Path(input_dir) if input_dir else out
    per_site_out = out / "per_site"
    per_site_out.mkdir(parents=True, exist_ok=True)

    lo_idp, hi_idp, lo_ids, hi_ids, lo_idt, hi_idt = _id_pools(digits)
    id_type  = "IDS" if anon else "IDP"
    lo_col   = lo_ids if anon else lo_idp
    hi_col   = hi_ids if anon else hi_idp
    id_visit = 1 if anon else 0

    use_groups         = "G" in blocks
    track_tag          = "+".join(track_names) if has_tracks else ""
    n_col_per_part     = len(track_names) if has_tracks else 1
    track_len_in_id    = 1 if has_tracks else 0   # 1-char abbreviation, or no T block

    g_col = ["Group"] if use_groups else []
    if has_tracks:
        file_header   = ["IDT"] + [f"{id_type}_{t}" for t in track_names] + g_col
        master_header = ["Site", "IDT"] + [f"{id_type}_{t}" for t in track_names] + g_col
    else:
        file_header   = ["IDT", id_type] + g_col
        master_header = ["Site", "IDT", id_type] + g_col

    # ── Planning phase: classify sites, collect existing numbers ──────────────
    plan = []
    used_idt: set = set()
    used_col: set = set()

    for site_name, n_cases, n_controls in samples:
        n_participants = n_cases + n_controls   # sum cases + controls
        if n_participants == 0:
            continue
        existing_file = _find_multitrack_site_file(study, site_name, track_tag, inp, id_type)
        if existing_file:
            with open(existing_file, encoding="utf-8", newline="") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader)  # skip header
                existing_rows = [r for r in reader if r]
            existing_n = len(existing_rows)
            s_len   = len(study)
            pos_idt = field_start(blocks, "N", len(center), 0, digits, study_len=s_len)
            for row in existing_rows:
                if pos_idt >= 0 and row[0]:
                    used_idt.add(int(row[0][pos_idt:pos_idt + digits]))
            g_len   = len(case_prefix) if use_groups else 0
            pos_col = field_start(blocks, "N", len(center), track_len_in_id, digits,
                                  group_len=g_len, study_len=s_len, site_len=len(site_name))
            if has_tracks:
                for i in range(len(track_names)):
                    for row in existing_rows:
                        if pos_col >= 0 and len(row) > i + 1 and row[i + 1]:
                            used_col.add(int(row[i + 1][pos_col:pos_col + digits]))
            else:
                for row in existing_rows:
                    if pos_col >= 0 and len(row) > 1 and row[1]:
                        used_col.add(int(row[1][pos_col:pos_col + digits]))
            plan.append(dict(site_name=site_name, add_n=n_participants,
                             n_cases=n_cases, n_controls=n_controls,
                             mode="extend", existing_n=existing_n,
                             existing_rows=existing_rows, existing_file=existing_file))
        else:
            plan.append(dict(site_name=site_name, add_n=n_participants,
                             n_cases=n_cases, n_controls=n_controls, mode="new"))

    if not plan:
        _log("ERROR: No valid sites found in input.")
        return False

    total_new_idt = sum(e["add_n"] for e in plan)
    total_new_col = total_new_idt * n_col_per_part

    tracks_label = ", ".join(track_names) if has_tracks else "(none — single IDS column)"
    _log(f"Tracks       : {tracks_label}")
    _log(f"ID type      : {id_type}  ({'anonymised cohort — no personal data' if anon else 'personal data tracked'})")
    _log(f"Sites        : {len(plan)}")
    _log(f"\n{'Site':<20} {'Action':<10} {'Add':>6} {'Existing':>9}")
    _log("-" * 52)
    for e in plan:
        ex_str = str(e.get("existing_n", "—")).rjust(9)
        _log(f"  {e['site_name']:<18} {e['mode']:<10} {e['add_n']:>6} {ex_str}")
    _log("-" * 52)
    _log(f"  New IDT to generate  : {total_new_idt}")
    col_detail = (f"  ({len(track_names)} tracks × {total_new_idt})" if has_tracks else "")
    _log(f"  New {id_type} to generate : {total_new_col}{col_detail}")
    _log()
    _log(f"ID-P pool : {lo_idp} – {hi_idp}")
    _log(f"ID-S pool : {lo_ids} – {hi_ids}")
    _log(f"ID-T pool : {lo_idt} – {hi_idt}\n")

    # ── Draw all new numbers globally in one pass ─────────────────────────────
    new_idt_pool = _unique_randoms(lo_idt, hi_idt, total_new_idt, used_idt)
    new_col_pool = _unique_randoms(lo_col, hi_col, total_new_col, used_col)

    ts = timestamp()
    idt_pos = 0
    col_pos = 0

    for e in plan:
        site_name = e["site_name"]
        add_n     = e["add_n"]
        mode      = e["mode"]

        idt_slice = new_idt_pool[idt_pos:idt_pos + add_n]
        idt_ids   = [build_id(blocks, center, "", n, 1, checksum_fn, study=study) for n in idt_slice]
        idt_pos  += add_n

        if has_tracks:
            col_by_track: dict = {}
            for t in track_names:
                col_slice = new_col_pool[col_pos:col_pos + add_n]
                col_pos  += add_n
                if use_groups:
                    n_c           = e.get("n_cases", add_n)
                    case_ids      = [build_id(blocks, center, t[0], n, id_visit, checksum_fn,
                                             study=study, site=site_name, group=case_prefix)
                                     for n in col_slice[:n_c]]
                    ctrl_ids      = [build_id(blocks, center, t[0], n, id_visit, checksum_fn,
                                             study=study, site=site_name, group=control_prefix)
                                     for n in col_slice[n_c:]]
                    col_by_track[t] = case_ids + ctrl_ids
                else:
                    col_by_track[t] = [build_id(blocks, center, t[0], n, id_visit, checksum_fn,
                                                study=study, site=site_name)
                                       for n in col_slice]
            if use_groups:
                n_c    = e.get("n_cases", add_n)
                groups = [case_prefix] * n_c + [control_prefix] * (add_n - n_c)
                new_rows = [[idt_ids[i]] + [col_by_track[t][i] for t in track_names] + [groups[i]]
                            for i in range(add_n)]
            else:
                new_rows = [[idt_ids[i]] + [col_by_track[t][i] for t in track_names]
                            for i in range(add_n)]
        else:
            col_slice = new_col_pool[col_pos:col_pos + add_n]
            col_pos  += add_n
            if use_groups:
                n_c      = e.get("n_cases", add_n)
                case_ids = [build_id(blocks, center, "", n, id_visit, checksum_fn,
                                     study=study, site=site_name, group=case_prefix)
                            for n in col_slice[:n_c]]
                ctrl_ids = [build_id(blocks, center, "", n, id_visit, checksum_fn,
                                     study=study, site=site_name, group=control_prefix)
                            for n in col_slice[n_c:]]
                col_ids  = case_ids + ctrl_ids
                groups   = [case_prefix] * n_c + [control_prefix] * (add_n - n_c)
                new_rows = [[idt_ids[i], col_ids[i], groups[i]] for i in range(add_n)]
            else:
                col_ids  = [build_id(blocks, center, "", n, id_visit, checksum_fn,
                                     study=study, site=site_name)
                            for n in col_slice]
                new_rows = [[idt_ids[i], col_ids[i]] for i in range(add_n)]

        if mode == "extend":
            all_file_rows = e["existing_rows"] + new_rows
            total_n       = e["existing_n"] + add_n
            suffix        = "Updated"
            action        = f"extended {e['existing_n']} → {total_n}"
            e["existing_file"].rename(e["existing_file"].with_suffix(".old"))
        else:
            all_file_rows = new_rows
            total_n       = add_n
            suffix        = "First"
            action        = f"{add_n} new"

        if has_tracks:
            per_site_file = per_site_out / (
                f"{ts}_{study}_{id_type}_T={track_tag}_SITE={site_name}_N={total_n}_{suffix}.txt"
            )
        else:
            per_site_file = per_site_out / (
                f"{ts}_{study}_{id_type}_IDT_SITE={site_name}_N={total_n}_{suffix}.txt"
            )
        _write_csv(per_site_file, file_header, all_file_rows)
        _log(f"  [{site_name}] {action}  →  per_site/{per_site_file.name}")

    # ── Rebuild master ALL by re-reading every current per-site file ──────────
    all_master_rows = []
    glob_pat = (f"*{study}_{id_type}_T={track_tag}_SITE=*.txt" if has_tracks
                else f"*{study}_{id_type}_IDT_SITE=*.txt")
    for f in sorted(per_site_out.glob(glob_pat)):
        site = get_param_from_filename(str(f), "SITE")
        with open(f, encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            next(reader)
            for cols in reader:
                if cols:
                    all_master_rows.append([site] + cols)

    old_glob     = (f"*_{study}_{id_type}_T={track_tag}_ALL_*.txt" if has_tracks
                    else f"*_{study}_{id_type}_IDT_ALL_*.txt")
    master_fname = (f"{ts}_{study}_{id_type}_T={track_tag}_ALL_N={len(all_master_rows)}.txt"
                    if has_tracks
                    else f"{ts}_{study}_{id_type}_IDT_ALL_N={len(all_master_rows)}.txt")

    for old in sorted(out.glob(old_glob)):
        old.rename(old.with_suffix(".old"))

    master_file = out / master_fname
    _write_numbered(master_file, master_header, all_master_rows)
    _log(f"  Master ALL : {master_file.name}")
    _log("Done.")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# F2. GENERATE FOLLOW-UPs
# ─────────────────────────────────────────────────────────────────────────────

def generate_followups(study, visit, input_dir, output_dir):
    """
    Generate follow-up IDs from existing IDS_IDT baseline files.

    Each follow-up ID is the baseline IDS ID prefixed with the visit tag, e.g.:
      Baseline IDS  : 01SiteAS123451X
      Visit 2 IDSV2 : V2_01SiteAS123451X
      Visit 3 IDSV3 : V3_01SiteAS123451X

    This makes the relationship explicit and prevents any confusion with baseline IDs.
    No new random numbers are drawn — all visit IDs are derived from existing baselines.
    """
    if visit < 2:
        _log("ERROR: --visit must be 2 or higher. Visit 1 is reserved for baseline IDS.")
        return False

    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    search_dirs = [inp, inp / "per_site"]
    baseline_files = sorted(
        f for d in search_dirs if d.exists()
        for sfx in ("First", "Updated")
        for f in d.glob(f"*{study}_IDS_IDT_*_{sfx}.txt")
        if "_ALL_" not in f.name
    )
    if not baseline_files:
        _log(f"ERROR: No baseline files found for study '{study}' in {inp}")
        return False

    followup_out = out / "followup"
    followup_out.mkdir(parents=True, exist_ok=True)

    ts = timestamp()
    visit_tag = f"V{visit}_"
    all_rows = []

    for bf in baseline_files:
        track_name = get_param_from_filename(str(bf), "T")
        group      = get_param_from_filename(str(bf), "G")

        with open(bf, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            if header != ["IDS", "IDS128", "IDT"]:
                _log(f"ERROR: Unexpected header in {bf.name}: {header}")
                return False
            rows = [r for r in reader if r]

        ids_ids  = [row[0] for row in rows]
        ids128   = [row[1] for row in rows]
        idsv_ids = [visit_tag + ids for ids in ids_ids]
        idsv128  = [format_code128(v) for v in idsv_ids]

        track_n = len(rows)
        g_tag   = f"_G={group}" if group else ""

        # Per-site file: keeps barcode columns for label printing
        per_site_file = followup_out / f"{ts}_{study}_IDS_IDSV{visit}_T={track_name}{g_tag}_N={track_n}_V={visit}.txt"
        _write_tsv(per_site_file,
                   ["IDS", f"IDSV{visit}", "IDS128", f"IDSV{visit}128"],
                   zip(ids_ids, idsv_ids, ids128, idsv128))

        for ids, idsv in zip(ids_ids, idsv_ids):
            all_rows.append((ids, idsv, track_name, group))

        label = f"{track_name}/{group}" if group else track_name
        _log(f"  [{label}] {track_n} follow-ups (V={visit})  →  followup/{per_site_file.name}")

    for old in sorted(out.glob(f"*_{study}_IDS_IDSV{visit}_ALL_*_V={visit}.txt")):
        old.rename(old.with_suffix(".old"))
    # ALL file: no barcode columns — clean IDs only, safe for Excel/R merging
    all_file = out / f"{ts}_{study}_IDS_IDSV{visit}_ALL_N={len(all_rows)}_V={visit}.txt"
    _write_numbered(all_file,
                    ["IDS", f"IDSV{visit}", "Track", "Group"],
                    all_rows)
    _log(f"  Master FOLLOWUP_ALL : {all_file.name}")

    _log("Done.")
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
        f = out / f"{ts}_{study}_{kind}_T={track_name}_N=0_First.txt"
        _write_tsv(f, header, [])
        _log(f"  Created {f.name}")

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

        idp_files = sorted(
            f for sfx in ("First", "Updated")
            for f in inp.glob(f"*{study}_IDP_IDT_*T={track_name}*_{sfx}.txt")
        )
        ids_files = sorted(
            f for sfx in ("First", "Updated")
            for f in inp.glob(f"*{study}_IDS_IDT_*T={track_name}*_{sfx}.txt")
        )

        if not idp_files:
            _log(f"ERROR: IDP baseline for track '{track_name}' not found in {inp}")
            return False

        actual_idp = count_data_lines(str(idp_files[0]))
        if actual_idp != existing_n:
            _log(f"ERROR: IDP file has {actual_idp} records, declared {existing_n}")
            return False

        group  = get_param_from_filename(str(idp_files[0]), "G")
        len_c  = len(center)
        len_t  = len(track_name)
        len_g  = len(group)
        pos_n  = field_start(blocks, "N", len_c, len_t, digits, group_len=len_g, study_len=len(study),
                             site_len=len_t)

        # IDS file is optional (only written when --shuffle was used originally)
        idt_to_ids_num = {}
        if ids_files:
            actual_ids = count_data_lines(str(ids_files[0]))
            if actual_ids != existing_n:
                _log(f"ERROR: IDS file has {actual_ids} records, declared {existing_n}")
                return False
            with open(ids_files[0], encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader)
                for row in reader:
                    if not row:
                        continue
                    ids_n = int(row[0][pos_n:pos_n + digits]) if pos_n >= 0 else 0
                    idt_n = int(row[2][pos_n:pos_n + digits]) if pos_n >= 0 else 0
                    idt_to_ids_num[idt_n] = ids_n

        idp_nums_existing = []
        idt_nums_existing = []
        with open(idp_files[0], encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader)
            for row in reader:
                if not row:
                    continue
                idp_nums_existing.append(int(row[0][pos_n:pos_n + digits]) if pos_n >= 0 else 0)
                idt_nums_existing.append(int(row[2][pos_n:pos_n + digits]) if pos_n >= 0 else 0)

        ids_nums_matched = []
        if idt_to_ids_num:
            for idt_n in idt_nums_existing:
                if idt_n not in idt_to_ids_num:
                    _log(f"ERROR: IDT {idt_n} in IDP file has no match in IDS file.")
                    return False
                ids_nums_matched.append(idt_to_ids_num[idt_n])

        new_idp = _unique_randoms(lo_idp, hi_idp, add_n, set(idp_nums_existing))
        new_ids = _unique_randoms(lo_ids, hi_ids, add_n, set(ids_nums_matched))
        new_idt = _unique_randoms(lo_idt, hi_idt, add_n, set(idt_nums_existing))

        all_idp_nums = idp_nums_existing + new_idp
        all_ids_nums = ids_nums_matched  + new_ids
        all_idt_nums = idt_nums_existing + new_idt

        idp_file, ids_file, _, _ = _write_baseline_for_track(
            study, center, track_name, group,
            total_n,
            all_idp_nums, all_ids_nums, all_idt_nums,
            blocks, checksum_fn, out, ts,
            shuffle=shuffle, suffix="Updated",
        )

        if ids_files:
            ids_files[0].rename(ids_files[0].with_suffix(".old"))
        idp_files[0].rename(idp_files[0].with_suffix(".old"))
        _log(f"  [{track_name}] extended {existing_n} → {total_n}")
        _log(f"    IDP→IDT : {idp_file.name}")
        _log(f"    IDS→IDT : {ids_file.name}")
        _log(f"    (old files renamed to .old)")

    _log("Done.")
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

    search_dirs = [inp, inp / "per_site"]
    baseline_files = sorted(
        f for d in search_dirs if d.exists()
        for sfx in ("First", "Updated")
        for f in d.glob(f"*{study}_IDS_IDT_*_{sfx}.txt")
        if "_ALL_" not in f.name
    )
    if not baseline_files:
        _log(f"ERROR: No baseline files found for study '{study}' in {inp}")
        return False

    ts = timestamp()

    for bf in baseline_files:
        track_name = get_param_from_filename(str(bf), "T")
        group      = get_param_from_filename(str(bf), "G")

        with open(bf, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            if header != ["IDS", "IDS128", "IDT"]:
                _log(f"ERROR: Unexpected header in {bf.name}: {header}")
                return False
            rows = [r for r in reader if r]

        track_n  = len(rows)
        ide_nums = _unique_randoms(lo_ide, hi_ide, track_n, set())

        ids_ids = [row[0] for row in rows]
        ids128  = [row[1] for row in rows]
        ide_ids = [build_id(blocks, center, track_name, n, 0, checksum_fn, group=group, study=study)
                   for n in ide_nums]
        ide128  = [format_code128(x) for x in ide_ids]

        g_tag    = f"_G={group}" if group else ""
        out_file = out / f"{ts}_{study}_IDS_IDE_T={track_name}{g_tag}_N={track_n}_{ext_project}.txt"
        _write_tsv(out_file, ["IDS", "IDE", "IDS128", "IDE128"],
                   zip(ids_ids, ide_ids, ids128, ide128))

        label = f"{track_name}/{group}" if group else track_name
        _log(f"  [{label}] {track_n} external IDs  →  {out_file.name}")

    _log("Done.")
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
    shared.add_argument("--study",    default=None,
                        help="Study name (loaded from study.cfg if omitted)")
    shared.add_argument("--center",   default=None,
                        help="Study center code (loaded from study.cfg if omitted)")
    shared.add_argument("--digits",   type=int, default=None,
                        help="Digits for unique number field (default: 5)")
    shared.add_argument("--blocks",   default=None,
                        help="Building block order, e.g. CTNVX or CTGNVX (default: CTNVX)")
    shared.add_argument("--checksum", default=None,
                        choices=list(CHECKSUMS.keys()) + [None],
                        help="Checksum algorithm (default: Damm_2004)")
    shared.add_argument("--output",   default=".",
                        help="Output / study directory (default: current directory)")
    shared.add_argument("--shuffle", action="store_true",
                        help="Also generate the row-shuffled IDS_IDT file.")
    shared.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible ID generation (optional).")

    # ── init ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("init",
                       help="Save study parameters to study.cfg — run once per project")
    p.add_argument("--study",    required=True)
    p.add_argument("--center",   default="", help="Study center code")
    p.add_argument("--digits",   type=int, default=5)
    p.add_argument("--blocks",   default="CRGNVX")
    p.add_argument("--checksum", default="Damm_2004", choices=list(CHECKSUMS.keys()))
    p.add_argument("--case-prefix",    default="S")
    p.add_argument("--control-prefix", default="C")
    p.add_argument("--tracks", default=None,
                   help="Default data tracks for multi-track batch runs "
                        "(e.g. 'Genetics,Phenotype'). Saved to study.cfg and picked up "
                        "automatically by every subsequent batch call. Override on the CLI "
                        "at any time to add new tracks.")
    p.add_argument("--anon", action="store_true",
                   help="Anonymised cohort: generate IDS (study data IDs) instead of "
                        "IDP (personal data IDs). Use when participants have no personal "
                        "data to track — only scientific data IDs are needed.")
    p.add_argument("--visit", type=int, default=2,
                   help="Follow-up visit number to use for all followup runs (default: 2)")
    p.add_argument("--output",   default=".", help="Study output directory")

    # ── baseline ─────────────────────────────────────────────────────────────
    p = sub.add_parser("baseline", parents=[shared],
                       help="Generate a fresh baseline for named tracks")
    p.add_argument("--tracks", required=True,
                   help="Track names. Multi-track mode (with --samplesize): comma-separated names "
                        "e.g. 'Genetics,Phenotype,Imaging'. "
                        "Single-track mode (without --samplesize): name:count pairs "
                        "e.g. 'TrackA:100,TrackB:200'.")
    p.add_argument("--samplesize", type=int, default=None,
                   help="Participant count for multi-track mode. Every participant gets an ID for "
                        "every track. Omit to use the old name:count format.")

    # ── batch ─────────────────────────────────────────────────────────────────
    p = sub.add_parser("batch", parents=[shared],
                       help="Generate baseline from a sample sheet or inline counts")
    p.add_argument("--input-file", default=None,
                   help="Sample sheet file (.txt .txt .txt .xlsx .xls). "
                        "Columns: SampleName, NCases, NControls")
    p.add_argument("--tracks", default=None,
                   help="Comma-separated data track names for multi-track mode "
                        "(e.g. 'Genetics,Phenotype'). The sheet defines sites and counts; "
                        "--tracks defines what IDP columns each participant receives. "
                        "Output per site: IDT | IDP_T1 | IDP_T2 | ...")
    p.add_argument("--samplesize", nargs="+", type=int, default=None,
                   help="Inline counts instead of an input file. "
                        "One value when --blocks has no G (e.g. --samplesize 5000). "
                        "Two values when --blocks has G (e.g. --samplesize 50 80 for NCases NControls).")
    p.add_argument("--site", default=None,
                   help="Recruitment site name embedded by the R block when using --samplesize (default: study name).")
    p.add_argument("--case-prefix",    default=None,
                   help="Single-letter prefix for case IDs (loaded from study.cfg if omitted)")
    p.add_argument("--control-prefix", default=None,
                   help="Single-letter prefix for control IDs (loaded from study.cfg if omitted)")
    p.add_argument("--fresh", action="store_true",
                   help="Force all rows to be created new, ignoring any existing baselines.")
    p.add_argument("--input-dir", default=None,
                   help="Where to look for existing baseline files. Defaults to --output.")

    # ── followup ─────────────────────────────────────────────────────────────
    p = sub.add_parser("followup", parents=[shared],
                       help="Generate follow-up visit IDs from existing baseline files")
    p.add_argument("--visit", type=int, default=None,
                   help="Follow-up visit number (default: loaded from study.cfg, fallback 2)")
    p.add_argument("--input-dir", default=None,
                   help="Directory containing baseline IDS_IDT files (default: .)")

    # ── add-track ─────────────────────────────────────────────────────────────
    p = sub.add_parser("add-track", parents=[shared],
                       help="Create an empty baseline file pair for a new track")
    p.add_argument("--track",  required=True, help="New track name")

    # ── extend ───────────────────────────────────────────────────────────────
    p = sub.add_parser("extend", parents=[shared],
                       help="Add new subjects to an existing baseline")
    p.add_argument("--tracks", default=None,
                   help="Single-track mode only: existing tracks and counts, "
                        "e.g. 'TrackA:100,TrackB:200'. Omit for multi-track mode "
                        "(tracks are read from the existing file automatically).")
    p.add_argument("--new-samples", required=True,
                   help="Multi-track mode: integer count of new participants to add. "
                        "Single-track mode: per-track counts, e.g. 'TrackA:20,TrackB:30'.")
    p.add_argument("--input-dir", default=None,
                   help="Directory containing the existing baseline files (default: .)")

    # ── external ─────────────────────────────────────────────────────────────
    p = sub.add_parser("external", parents=[shared],
                       help="Create external-project IDs linked to an existing baseline")
    p.add_argument("--ext-project", required=True,
                   help="External project name (used in filenames)")
    p.add_argument("--input-dir", default=None)

    args = parser.parse_args()

    # ── Load study.cfg and fill in any missing args ───────────────────────────
    out_dir = getattr(args, "output", ".")
    cfg = _load_config(out_dir)
    if cfg:
        _apply_config(args, cfg)

    # Apply hardcoded defaults for anything still None after config load
    _defaults = dict(center="", digits=5, blocks="CRGNVX",
                     checksum="Damm_2004", case_prefix="S", control_prefix="C", visit=2)
    for attr, val in _defaults.items():
        if getattr(args, attr, None) is None:
            setattr(args, attr, val)

    # ── Handle init before logging (no output dir needed yet) ─────────────────
    if args.command == "init":
        cfg_data = {
            "study":           args.study,
            "center":          args.center,
            "digits":          args.digits,
            "blocks":          args.blocks,
            "checksum":        args.checksum,
            "case_prefix":     args.case_prefix,
            "control_prefix":  args.control_prefix,
            "visit":           args.visit,
            "output":          args.output,
        }
        if getattr(args, "tracks", None):
            cfg_data["tracks"] = args.tracks
        if getattr(args, "anon", False):
            cfg_data["anon"] = True
        if "T" in args.blocks and not getattr(args, "tracks", None):
            print("WARNING: T is in --blocks but --tracks is not declared. "
                  "T embeds a data-track abbreviation and has no meaning without --tracks. "
                  "Use R for the recruitment site instead, or add --tracks.")
        _save_config(cfg_data, args.output)
        if cfg:
            print("Previous config overwritten.")
        sys.exit(0)

    # ── Seed and logging ──────────────────────────────────────────────────────
    seed = getattr(args, "seed", None)
    if seed is not None:
        random.seed(seed)

    _log_init(out_dir)
    if seed is not None:
        _log(f"Random seed  : {seed}")
    _log(f"{'='*60}")
    _log(f"Command  : {args.command}")
    _log(f"Arguments: {' '.join(sys.argv[1:])}")
    if cfg:
        _log(f"Config   : loaded from {Path(out_dir) / CONFIG_FILENAME}")
    _log(f"{'='*60}")

    if args.command == "baseline":
        if args.samplesize is not None:
            track_names = [t.strip() for t in args.tracks.split(",")]
            ok = generate_multitrack_baseline(
                args.study, args.center, track_names, args.samplesize,
                args.digits, args.blocks, args.checksum, args.output)
        else:
            ok = generate_baseline(args.study, args.center, _parse_tracks(args.tracks),
                                   args.digits, args.blocks, args.checksum, args.output,
                                   shuffle=args.shuffle)

    elif args.command == "batch":
        if args.input_file is None and args.samplesize is None:
            parser.error("batch requires either --input-file or --samplesize")

        # Auto-load tracks from study.cfg when not supplied on the command line
        if not getattr(args, "tracks", None) and cfg.get("tracks"):
            args.tracks = cfg["tracks"]

        if "T" in args.blocks and not getattr(args, "tracks", None) and not cfg.get("tracks"):
            _log("WARNING: T is in --blocks but no --tracks are declared. "
                 "T will repeat the site name — use R for site, or declare --tracks at init.")

        if args.tracks or cfg.get("anon", False):
            # ── Multi-track or anonymised mode ────────────────────────────────
            # args.tracks already auto-loaded from cfg above; may still be None
            # for --anon with no tracks (→ single plain IDS column, track_names=[]).
            track_names = ([t.strip() for t in args.tracks.split(",")]
                           if args.tracks else [])
            if args.samplesize is not None:
                site_name = args.site or args.study
                ss = args.samplesize
                if track_names and len(ss) != 1:
                    _log("ERROR: --tracks with --samplesize expects a single participant count.")
                    sys.exit(1)
                mt_samples = [(site_name, ss[0], ss[1] if len(ss) > 1 else 0)]
            else:
                try:
                    mt_samples = read_sample_sheet(args.input_file)
                except (ValueError, ImportError) as e:
                    _log(f"ERROR: {e}")
                    sys.exit(1)
            ok = _generate_batch_multitrack(
                args.study, args.center, mt_samples, track_names,
                args.digits, args.blocks, args.checksum,
                args.output, args.input_dir or args.output,
                anon=cfg.get("anon", False),
                case_prefix=args.case_prefix, control_prefix=args.control_prefix)
        else:
            # ── Standard batch mode: case/control per site ────────────────────
            inline_samples = None
            if args.samplesize is not None:
                track_name = args.site or args.study
                has_g = "G" in (args.blocks or "")
                ss = args.samplesize
                if has_g:
                    if len(ss) != 2:
                        _log("ERROR: --blocks contains G (case/control mode); "
                             "--samplesize requires two values: NCases NControls")
                        sys.exit(1)
                    inline_samples = [(track_name, ss[0], ss[1])]
                else:
                    if len(ss) != 1:
                        _log("ERROR: --blocks does not contain G (single-group mode); "
                             "--samplesize requires one value: N")
                        sys.exit(1)
                    inline_samples = [(track_name, ss[0], 0)]

            ok = generate_batch(args.study, args.center, args.input_file,
                                args.digits, args.blocks, args.checksum,
                                args.case_prefix, args.control_prefix, args.output,
                                extend_mode=not args.fresh,
                                input_dir=args.input_dir or args.output,
                                shuffle=args.shuffle,
                                samples=inline_samples)

    elif args.command == "followup":
        ok = generate_followups(args.study, args.visit,
                                args.input_dir or args.output, args.output)

    elif args.command == "add-track":
        if not args.study:
            parser.error("add-track requires --study (or a study.cfg in the output directory)")
        ok = add_track(args.study, args.track, args.output, shuffle=args.shuffle)

    elif args.command == "extend":
        if args.tracks is None:
            # Multi-track mode: --new-samples is a plain integer count
            try:
                add_n = int(args.new_samples)
            except ValueError:
                _log("ERROR: Multi-track extend requires --new-samples to be an integer count.")
                sys.exit(1)
            ok = extend_multitrack_baseline(
                args.study, args.center, add_n,
                args.digits, args.blocks, args.checksum,
                args.input_dir or args.output, args.output)
        else:
            tracks      = _parse_tracks(args.tracks)
            new_samples = dict(_parse_tracks(args.new_samples))
            ok = extend_baseline(args.study, args.center, tracks, new_samples,
                                 args.digits, args.blocks, args.checksum,
                                 args.input_dir or args.output, args.output,
                                 shuffle=args.shuffle)

    elif args.command == "external":
        ok = create_external_ids(args.study, args.center, args.ext_project,
                                 args.digits, args.blocks, args.checksum,
                                 args.input_dir or args.output, args.output)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
