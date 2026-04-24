#!/usr/bin/env bash
# Scenario 2 — Multi-track anonymised cohort, sheet-based input
#
# IMPORTANT: tracks must be decided before the first batch run.
#   Every participant enrolled under a given track set gets IDS IDs for ALL
#   of those tracks. You cannot add a track to existing participants later —
#   doing so would require a new separate dataset (different track tag),
#   leaving prior participants without the new track column.
#   If you know you will need Genetics + Phenotype, declare both at init.
#
# --anon   : no personal data tracked — IDS (study data IDs) generated, not IDP.
# --tracks : track list declared once at init, auto-loaded by every batch call.
#
# Run from the idGenerator_python/ directory.

set -e

# Step 1 — save study parameters and declare the starting track
#   --anon and --tracks are stored in study.cfg; all future batch calls use them.
#   Declare ALL tracks you will need before the first batch run (see note above).
python3 idgenerator.py init \
    --study    AnonymCohort \
    --center   01 \
    --digits   5 \
    --blocks   CRTNVX \
    --checksum Damm_2004 \
    --tracks   Genetics \
    --anon \
    --output   test_scenario2/ids

# Step 2 — generate IDS IDs from a sample sheet; extend with more samples later
#
#   Wave 1 — initial enrolment from sheet.
#   wave1.txt defines sites and participant counts:
#     SiteA  200 cases, 0  controls  →  200 participants, no case/control split
#     SiteB  150 cases, 75 controls  →  225 participants, case/control split
#   Output per site: IDT | IDS_Genetics | IDS_Phenotype
#
python3 idgenerator.py batch \
    --input-file test_scenario2/wave1.txt \
    --output     test_scenario2/ids \
    --seed 10

#   Wave 2 — additional participants at the same sites (SiteA +50, SiteB +30).
#   The script finds the existing per-site files and appends automatically.
python3 idgenerator.py batch \
    --input-file test_scenario2/wave2.txt \
    --output     test_scenario2/ids \
    --seed 11

# Step 3 — starting a NEW parallel dataset with a different track combination
#
#   This is NOT adding a track to existing participants — it is a fresh start
#   for a new track set. Existing participants keep only the tracks they were
#   enrolled under. The two datasets are independent and can be linked via IDT.
#
#   Use this only if you are beginning a genuinely new data collection effort
#   (e.g. an imaging sub-study added mid-project with its own enrolment list).
#
#   python3 idgenerator.py init \
#       --study    AnonymCohort \
#       --center   01 \
#       --digits   5 \
#       --blocks   CRTNVX \
#       --checksum Damm_2004 \
#       --tracks   Genetics,Phenotype,Imaging \
#       --anon \
#       --output   test_scenario2/ids
#
#   python3 idgenerator.py batch \
#       --input-file test_scenario2/wave3.txt \
#       --output     test_scenario2/ids \
#       --seed 12
