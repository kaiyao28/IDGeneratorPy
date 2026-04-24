#!/usr/bin/env bash
# Full multi-site, multi-wave example with case/control groups and follow-up.
# Covers: batch (new + auto-extend + shuffle), followup.
# Run from the idGenerator_python/ directory.

set -e

# Step 1 — save study parameters
python3 idgenerator.py init \
    --study    TestStudy \
    --center   01 \
    --digits   5 \
    --blocks   CRGNVX \
    --checksum Damm_2004 \
    --case-prefix    S \
    --control-prefix C \
    --visit    2 \
    --output   Test_Scripts/test_full/ids

# Step 2 — Wave 1: SiteA (20S/40C), SiteB (15S/30C), SiteC (10S/20C) — all new
python3 idgenerator.py batch \
    --input-file Test_Scripts/test_full/wave1.txt \
    --output     Test_Scripts/test_full/ids \
    --seed 42

# Step 3 — Wave 2: extend SiteA (5S/10C), add new SiteD (8S/16C)
python3 idgenerator.py batch \
    --input-file Test_Scripts/test_full/wave2.txt \
    --output     Test_Scripts/test_full/ids \
    --seed 43

# Step 4 — Wave 3: add new SiteE (6S/12C) with shuffled IDS row order
python3 idgenerator.py batch \
    --input-file Test_Scripts/test_full/wave3.txt \
    --output     Test_Scripts/test_full/ids \
    --shuffle \
    --seed 44

# Step 5 — follow-up visit 2 for all sites
python3 idgenerator.py followup \
    --output Test_Scripts/test_full/ids
