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

For `SCTNVX` with `--study MyStudy --center 01`, a case participant at SiteA gets `MyStudy01SiteA`**`S`**`12345`**`1X`** — each segment comes directly from its flag. The track (`T`) is the site name from the input sheet; the group (`G`) is the case prefix (default `S`) or control prefix (default `C`), both changeable at `init` with `--case-prefix` and `--control-prefix`.

`N` is the only required block — it is the unique random number that makes each ID distinct. All other blocks are optional prefixes around it.

**`--digits`** sets how many digits `N` uses (default `5`), which determines your maximum total enrolment across all waves:

| `--digits` | Max participants |
|-----------|----------------|
| `5` (default) | ~30,000 |
| `6` | ~300,000 |
| `7` | ~3,000,000 |

Set this once at `init` and do not change it — all IDs in a study must use the same digit count. Follow-up visits do not count toward the limit. See [REFERENCE.md](REFERENCE.md) for full details.

---

## Scenario 1 — Assign IDs by count

Use this when you are recruiting participants into a new study and want to assign IDP + IDS + IDT as people enrol. IDs are generated in batches; later waves extend the existing records automatically — no ID is ever reused. Deleting the IDT column at any point fully severs the link between personal and study data.

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
