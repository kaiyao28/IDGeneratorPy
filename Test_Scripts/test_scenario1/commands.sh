#!/usr/bin/env bash
# Scenario 1 — Inline sample size with named site
#
# --samplesize passes counts directly; no input file needed.
# --site sets the recruitment site name embedded by the R block. Without it,
#   the study name is used. The name must match across waves — whether you
#   extend manually (--site) or via a sheet (SampleName column), the script
#   finds the existing file by site name.
#
# Manual and sheet input can be freely mixed between waves:
#   Wave 1 manual → Wave 2 sheet  OR  Wave 1 sheet → Wave 2 manual
#   as long as SampleName in the sheet matches the --site value used manually.
#
# Run from the idGenerator_python/ directory.

set -e

# Step 1 — save study parameters
python3 idgenerator.py init \
    --study    Cohort1 \
    --center   01 \
    --digits   5 \
    --blocks   CRGNVX \
    --checksum Damm_2004 \
    --case-prefix    S \
    --control-prefix C \
    --output   Test_Scripts/test_scenario1/ids

# Step 2 — Wave 1: 50 cases and 80 controls at SiteA (manual input)
#   --site sets the recruitment site name for the R block and the output filename.
#   Omit --site to use the study name as the site label.
python3 idgenerator.py batch \
    --samplesize 50 80 \
    --site    SiteA \
    --output  Test_Scripts/test_scenario1/ids \
    --seed 1

# Step 3 — Wave 2: extend SiteA with 10 more cases and 20 more controls (manual)
#   --site SiteA matches the existing file — auto-extends.
python3 idgenerator.py batch \
    --samplesize 10 20 \
    --site    SiteB \
    --output  Test_Scripts/test_scenario1/ids \
    --seed 2

# Step 4 — Wave 3: extend via sheet input (SampleName must match --site above)
#   wave3.txt:
#     SampleName  NCases  NControls
#     SiteA       5       10
#   The script finds the SiteA file automatically and appends.
#
# python3 idgenerator.py batch \
#     --input-file Test_Scripts/test_scenario1/wave3.txt \
#     --output     Test_Scripts/test_scenario1/ids \
#     --seed 3

# Step 5 — follow-up visit 2
python3 idgenerator.py followup \
    --visit 2 \
    --output Test_Scripts/test_scenario1/ids

# Step 6 — follow-up visit 3
python3 idgenerator.py followup \
    --visit 3 \
    --output Test_Scripts/test_scenario1/ids
