#!/usr/bin/env bash
# Scenario 1 — Single cohort, inline sample size
# No input file needed — counts are passed directly on the command line.
# Run from the idGenerator_python/ directory.

set -e

# Step 1 — save study parameters
# --visit is omitted here; follow-up visit numbers are specified explicitly
# when you run followup, so you are not locked in at the start.
python3 idgenerator.py init \
    --study    Cohort1 \
    --center   01 \
    --digits   5 \
    --blocks   CTGNVX \
    --checksum Damm_2004 \
    --case-prefix    S \
    --control-prefix C \
    --output   test_scenario1/ids

# Step 2 — generate IDs for 50 cases and 80 controls (no input file)
python3 idgenerator.py batch \
    --samplesize 50 80 \
    --output test_scenario1/ids \
    --seed 1

# Step 3 — add 10 cases and 20 controls in a later wave (auto-extends)
python3 idgenerator.py batch \
    --samplesize 10 20 \
    --output test_scenario1/ids \
    --seed 2

# Step 4 — add follow-up visit 2 when that time point is reached
python3 idgenerator.py followup \
    --visit 2 \
    --output test_scenario1/ids

# Step 5 — add follow-up visit 3 at a later time point; visit 2 is untouched
python3 idgenerator.py followup \
    --visit 3 \
    --output test_scenario1/ids
