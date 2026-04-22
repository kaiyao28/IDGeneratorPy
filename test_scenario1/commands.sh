#!/usr/bin/env bash
# Scenario 1 — Single cohort, inline sample size
# No input file needed — counts are passed directly on the command line.
# Run from the idGenerator_python/ directory.

set -e

# Step 1 — save study parameters
python3 idgenerator.py init \
    --study    Cohort1 \
    --center   01 \
    --digits   5 \
    --blocks   CTGNVX \
    --checksum Damm_2004 \
    --case-prefix    S \
    --control-prefix C \
    --visit    2 \
    --output   test_scenario1/ids

# Step 2 — generate IDs for 50 cases and 80 controls (no input file)
python3 idgenerator.py batch \
    --samplesize 50 80 \
    --blocks CTGNVX \
    --output test_scenario1/ids \
    --seed 1

# Step 3 — add 10 cases and 20 controls in a later wave (auto-extends)
python3 idgenerator.py batch \
    --samplesize 10 20 \
    --blocks CTGNVX \
    --output test_scenario1/ids \
    --seed 2

# Step 4 — generate follow-up visit 2
python3 idgenerator.py followup \
    --output test_scenario1/ids
