#!/usr/bin/env bash
# Scenario 2 — Multiple data types in an anonymised cohort
# Tracks produce independent, unlinkable ID sets per data type.
# Run from the idGenerator_python/ directory.

set -e

# Step 1 — save study parameters (no G in blocks — no case/control distinction)
python3 idgenerator.py init \
    --study    AnonymCohort \
    --center   01 \
    --digits   5 \
    --blocks   CTNVX \
    --checksum Damm_2004 \
    --visit    2 \
    --output   test_scenario2/ids

# Step 2 — generate IDs for three data types in one command
python3 idgenerator.py baseline \
    --tracks "Genetics:500,Phenotype:500,Imaging:300" \
    --output test_scenario2/ids \
    --seed 10

# Step 3 — extend two tracks when new participants are added
python3 idgenerator.py extend \
    --tracks      "Genetics:500,Phenotype:500,Imaging:300" \
    --new-samples "Genetics:100,Phenotype:100" \
    --input-dir   test_scenario2/ids \
    --output      test_scenario2/ids \
    --seed 11

# ── Multi-site variant (optional) ────────────────────────────────────────────
# Uses tracks.txt where each row is a site x data-type combination.
# NControls=0 rows are skipped automatically.

# python3 idgenerator.py batch \
#     --input-file test_scenario2/tracks.txt \
#     --blocks CTNVX \
#     --output test_scenario2/ids_multisite \
#     --seed 12
