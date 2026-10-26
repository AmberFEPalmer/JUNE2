# EpiBench H3a: JUNE2 outbreaks matched to MetaWards

This folder is an addition to JUNE2 (IDAS-Durham/JUNE2, GPL-3.0) for EpiBench's hypothesis
H3a: do forecasting models trained on MetaWards keep their ranking on outbreaks from a
different simulator? No upstream file is modified. Everything here is GPL-3.0, like JUNE2.

It needs JUNE2 built as upstream describes, and the full-England world
`worlds/world_2021.h5` (not in the repo; built with MAY).

## What the 15 outbreaks are

3 speeds × 5 start locations, matching the 15 MetaWards outbreaks:

| Setting | Matched to MetaWards | Target doubling time | Fit window (national infections/day) | Full run |
|---|---|---|---|---|
| R13 | R0 1.3 | 18.90 days | 1,000 – 18,304 | 650 days |
| R18 | R0 1.8 | 8.61 days | 1,000 – 72,431 | 400 days |
| R25 | R0 2.5 | 5.33 days | 1,000 – 144,907 | 300 days |

| Replicate | MetaWards start ward | Seed MSOA (20 infections) |
|---|---|---|
| 1 | Lancaster Gate, Westminster | E02000976 (Westminster 017) |
| 2 | Cheetham, Manchester | E02006915 (Manchester 058) |
| 3 | Nechells, Birmingham | E02001878 (Birmingham 052) |
| 4 | Bude North and Stratton, Cornwall | E02003931 (Cornwall 001) |
| 5 | Myton, Hull | E02002680 (Kingston upon Hull 029) |

Each configuration (`make_h3a_config.py`) starts from `configs/config_2021` and changes only:
start 2020-01-01; no interventions (self-isolation, masks and distancing removed; hospital
admission of severe cases kept); permanent immunity (level 1.0, no waning); every beta
multiplied by one factor; 20 infections seeded in the start MSOA on day 0; its own random
seed; contact-event logging and checkpoints off. JUNE2's disease course is kept as it is:
that difference from MetaWards is part of what H3a tests.

Random seeds: `<setting number><replicate>`, e.g. R18 replicate 3 → 1803, R25 replicate 1 → 2501.

## 1. Time one run first

Full England is large. Before anything else, run one short configuration to see the cost:

```bash
python epibench/make_h3a_config.py --out configs/epibench_h3a/test --beta-scale 1.0 \
    --days 30 --seed-msoa E02000976 --run-seed 1
mpirun -n 4 ./build/disease_sim --world worlds/world_2021.h5 \
    --config configs/epibench_h3a/test/simulation.yaml --run-id h3a_test
```

## 2. Calibrate the speed (one factor per setting)

JUNE2 has no R0 setting, and its infectious period is longer than MetaWards', so equal R0
would not give equal speed. Instead, find the beta multiplier `K` that gives each setting's
target doubling time. Use replicate 1's seed MSOA for calibration. Runs only need to last
until national infections pass the top of the fit window (roughly 90 days for R25, 130 for
R18, 220 for R13); the export script says if a run stopped too early.

```bash
python epibench/make_h3a_config.py --out configs/epibench_h3a/cal_R18_k1.0 --beta-scale 1.0 \
    --days 130 --seed-msoa E02000976 --run-seed 1801
mpirun -n 4 ./build/disease_sim --world worlds/world_2021.h5 \
    --config configs/epibench_h3a/cal_R18_k1.0/simulation.yaml --run-id cal_R18_k1.0
python epibench/export_daily_infections.py --world worlds/world_2021.h5 \
    --events runs/cal_R18_k1.0/simulation_events.h5 --out cal_R18_k1.0.csv --doubling-upper 72431
```

Try a few values of `K` that bracket the target (faster spread → shorter doubling time),
interpolate, then confirm with one run. Accept a `K` within ±5% of the target. Record the
final `K` for each setting.

## 3. Run the 15 outbreaks

For each setting and replicate, with that setting's `K`:

```bash
python epibench/make_h3a_config.py --out configs/epibench_h3a/R18_rep3 --beta-scale <K> \
    --days 400 --seed-msoa E02001878 --run-seed 1803
mpirun -n 4 ./build/disease_sim --world worlds/world_2021.h5 \
    --config configs/epibench_h3a/R18_rep3/simulation.yaml --run-id R18_rep3
python epibench/export_daily_infections.py --world worlds/world_2021.h5 \
    --events runs/R18_rep3/simulation_events.h5 --out R18_rep3_daily_msoa.csv --days 400
```

## 4. Hand over

Send the 15 `*_daily_msoa.csv` files, each setting's `K`, and this repo's commit hash
(`git rev-parse HEAD`). In EpiBench, each becomes a dataset with:

```bash
python synthetic/make_june.py convert R18_rep3_daily_msoa.csv --r0 R18 --rep 3 \
    --beta-scale <K> --run-seed 1803 --june-commit <hash>
```

which sums the MSOAs to the 326 English 2011 districts and applies EpiBench's observation
layer (30% reported, ~9-day delay), exactly as for MetaWards.
