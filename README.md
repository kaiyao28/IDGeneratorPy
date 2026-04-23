# IDGeneratorPy

Cross-platform Python port of [idGenerator](https://github.com/mpmky/idGenerator) (Olden et al. 2016, University of Regensburg). Generates randomized participant IDs (IDP / IDS / IDT) for clinical and epidemiological studies. Deleting the IDT linkage column fully severs the link between personal and study data.

> Full command reference, flag descriptions, and a multi-wave worked example: [REFERENCE.md](REFERENCE.md)  
> Changes and new features relative to the original VB.NET programme: [CHANGES.md](CHANGES.md)

---

## Requirements

- Python 3.7+
- Excel input (`.xlsx`): `pip install openpyxl`

---

## Setup — save study parameters once

```bash
git clone https://github.com/kaiyao28/IDGeneratorPy.git
cd IDGeneratorPy

python3 idgenerator.py init \
    --study  MyStudy \
    --center 01 \
    --blocks SCTNVX \
    --output ./ids
```

`init` writes `study.cfg`; every subsequent command loads it automatically. Set `--blocks`, `--digits`, `--checksum` here — not on every batch call.

**`--blocks`** controls what goes into each ID. Every block is optional except `N` (the unique random number):

| Block | Adds to ID | Include when… |
|-------|-----------|---------------|
| `S` | Study name | IDs from different studies may mix |
| `C` | Center code | Multi-center study |
| `T` | Track / sample name | Multiple sample types |
| `G` | Case (`S`) or control (`C`) prefix | Case/control distinction needed in ID |
| `N` | Unique random number | **Always required** |
| `V` | Visit digit (`0`=IDP, `1`=IDS) | Useful when IDP and IDS coexist |
| `X` | Check digit | Recommended if IDs are hand-transcribed on labels |

Examples:

| `--blocks` | Example ID | Use case |
|------------|-----------|---------|
| `SCTNVX` | `MyStudy01SiteAS123451X` | Full: study + center + track + group + checksum |
| `CTNVX` | `01SiteA123451X` | Standard single-study batch |
| `CTGNVX` | `01SiteAS123451X` | Standard batch with case/control |
| `SCN` | `MyStudy0112345` | Minimal anonymised cohort (Scenario 2) |

See [REFERENCE.md](REFERENCE.md) for full details.

---

## Scenario 1 — Assign IDs by count

Run `init` first (see above), then:

```bash
# All participants in one group
python3 idgenerator.py batch --samplesize 5000 --output ./ids

# Cases and controls (--blocks CTGNVX set at init)
python3 idgenerator.py batch --samplesize 50 80 --output ./ids
```

**Extend in a later wave** — pass the *additional* count; existing records are preserved automatically:

```bash
python3 idgenerator.py batch --samplesize 10 20 --output ./ids
```

---

## Scenario 2 — Assign IDS keys to an anonymised cohort

Use this when participants are already anonymous and you need uniform study-wide linkage keys. `--anon` tells the script to generate IDS (study data IDs) only — no personal IDP is created.

```bash
python3 idgenerator.py init \
    --study  AnonymCohort \
    --center 01 \
    --blocks SCN \
    --anon \
    --output ./ids
```

`--blocks SCN` is the minimal setting for an anonymised cohort: study prefix + center + random number. No track in the ID (tracks are separate columns), no visit digit (follow-ups use a `V2_` prefix), no checksum. Add `X` if IDs will be printed on tube labels.

Prepare a site sheet (`wave1.txt`):

```
SampleName   NCases   NControls
SiteA        200      0
SiteB        150      75
```

Generate IDs:

```bash
python3 idgenerator.py batch --input-file wave1.txt --output ./ids --seed 10
```

**Extend** with a new sheet of *additional* counts:

```bash
python3 idgenerator.py batch --input-file wave2.txt --output ./ids --seed 11
```

**Tracks** — if different data types (genetics, phenotyping…) need separate independent ID sets, declare them at `init` with `--tracks Genetics,Phenotype`. Each participant then gets `IDS_Genetics` and `IDS_Phenotype` columns. Tracks must be declared before the first batch run. See [REFERENCE.md](REFERENCE.md) for details.

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
