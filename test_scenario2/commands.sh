#!/usr/bin/env bash
# Scenario 2 — Multi-track anonymised cohort, sheet-based input
#
# Tracks are declared once at init and stored in study.cfg.
# Every subsequent batch call reads them automatically — no need to repeat.
# NControls=0 throughout: no case/control distinction, all participants are equal.
# Each participant receives one IDT (linkage key) and one IDP per track.
# No IDS or follow-up: this is an anonymised cohort with no personal data tracked.
#
# Run from the idGenerator_python/ directory.

set -e

# Step 1 — save study parameters and declare data tracks
#   --tracks is stored in study.cfg; all future batch calls use it automatically.
python3 idgenerator.py init \
    --study    AnonymCohort \
    --center   01 \
    --digits   5 \
    --blocks   CTNVX \
    --checksum Damm_2004 \
    --tracks   Genetics,Phenotype \
    --output   test_scenario2/ids

# Step 2 — Wave 1: generate IDs for two sites
#   wave1.txt has two rows (SiteA 200, SiteB 150); tracks come from study.cfg.
#   Output per site: IDT | IDP_Genetics | IDP_Phenotype
python3 idgenerator.py batch \
    --input-file test_scenario2/wave1.txt \
    --output     test_scenario2/ids \
    --seed 10

# Step 3 — Wave 2: extend both sites with additional participants
#   wave2.txt lists the same sites with new counts (SiteA +50, SiteB +30).
python3 idgenerator.py batch \
    --input-file test_scenario2/wave2.txt \
    --output     test_scenario2/ids \
    --seed 11

# --- Adding a new track later (optional) ---
#
# If a new data type (e.g. Imaging) is collected later, update init to record
# the new track set in study.cfg, then enrol the next wave under all three tracks.
# Existing Genetics+Phenotype files are left untouched; the new three-track files
# are written alongside them and linked via IDT.
#
#   python3 idgenerator.py init \
#       --study    AnonymCohort \
#       --center   01 \
#       --digits   5 \
#       --blocks   CTNVX \
#       --checksum Damm_2004 \
#       --tracks   Genetics,Phenotype,Imaging \
#       --output   test_scenario2/ids
#
#   python3 idgenerator.py batch \
#       --input-file test_scenario2/wave3.txt \
#       --output     test_scenario2/ids \
#       --seed 12
