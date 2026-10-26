"""
Daily new infections per MSOA (MGU) from one JUNE2 run, for EpiBench's H3a datasets.
Each infection is counted on the day it happened, in the MSOA where the infected person
lives (their geo unit, walked up the world's geography to the MGU level). Writes a wide CSV:
one row per day from 0 to the last simulated day, one column per MSOA code.

    python epibench/export_daily_infections.py --world worlds/world_2021.h5 \
        --events runs/R18_rep1/simulation_events.h5 --out R18_rep1_daily_msoa.csv \
        [--days 400] [--doubling-upper 72431]

--doubling-upper prints the national doubling time, fitted from 1,000 infections/day up to
that value, the same way EpiBench measures MetaWards (calibration targets in README.md).
Needs h5py and numpy (both in environment.yml).
"""
import argparse
import csv

import h5py
import numpy as np


def _strings(dataset):
    return [v.decode() if isinstance(v, bytes) else str(v) for v in dataset[:]]


# geo unit id -> name of its ancestor at `level` (e.g. the MSOA code of a small area)
def unit_to_level(world_path, level="MGU"):
    with h5py.File(world_path, "r") as f:
        ids = f["/geography/ids"][:]
        names = _strings(f["/metadata/names/geography"] if "/metadata/names/geography" in f
                         else f["/geography/names"])
        levels = f["/geography/levels"][:]
        parents = f["/geography/parent_ids"][:]
        level_names = _strings(f["/metadata/registries/geo_levels"])
    target = level_names.index(level)
    row = {int(i): k for k, i in enumerate(ids)}
    out = {}
    ### units above `level` (local authorities, regions) reach the top without meeting it: skipped
    for i in ids:
        k = row[int(i)]
        while levels[k] != target and int(parents[k]) in row:
            k = row[int(parents[k])]
        if levels[k] == target:
            out[int(i)] = names[k]
    return out


# National doubling time from 1,000/day to `upper`, before the peak (as EpiBench's make_june.py)
def doubling_time(daily, upper, lower=1000):
    x = np.asarray(daily, dtype=float)
    pre = x[:int(x.argmax()) + 1]
    idx = np.flatnonzero((pre >= lower) & (pre <= upper))
    if len(idx) < 5:
        raise ValueError(f"only {len(idx)} days between {lower} and {upper:.0f} infections/day; run longer")
    return float(np.log(2) / np.polyfit(idx, np.log(x[idx]), 1)[0])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--world", required=True)
    p.add_argument("--events", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--days", type=int, help="pad to this many days (default: the last infection's day)")
    p.add_argument("--doubling-upper", type=float)
    args = p.parse_args()

    with h5py.File(args.events, "r") as f:
        inf = f["events/infections"].fields(["person_id", "time"])[:]
        people = f["lookups/people"].fields(["person_id", "geo_unit_id"])[:]

    ### infected person -> home geo unit -> MSOA column, vectorised (tens of millions of rows)
    order = np.argsort(people["person_id"])
    pid, geo = people["person_id"][order], people["geo_unit_id"][order]
    pos = np.minimum(np.searchsorted(pid, inf["person_id"]), len(pid) - 1)
    if not (pid[pos] == inf["person_id"]).all():
        raise ValueError(f"{int((pid[pos] != inf['person_id']).sum())} infected people are missing from lookups/people")
    msoa_of = unit_to_level(args.world)
    codes = sorted(set(msoa_of.values()))
    unit_ids = np.array(sorted(msoa_of))
    homeless = ~np.isin(geo[pos], unit_ids)
    if homeless.any():
        raise ValueError(f"{int(homeless.sum())} infections are in geo units with no MGU above them, "
                         f"e.g. unit {int(geo[pos][homeless][0])}")
    column = {c: k for k, c in enumerate(codes)}
    unit_col = np.array([column[msoa_of[u]] for u in unit_ids.tolist()])
    col = unit_col[np.searchsorted(unit_ids, geo[pos])]

    day = np.floor(inf["time"]).astype(int)
    n_days = max(args.days or 0, int(day.max()) + 1)
    counts = np.zeros((n_days, len(codes)), dtype=np.int64)
    np.add.at(counts, (day, col), 1)

    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["day", *codes])
        w.writerows([d, *row] for d, row in enumerate(counts.tolist()))
    national = counts.sum(axis=1)
    print(f"{args.out}: {n_days} days x {len(codes)} MSOAs, {int(national.sum()):,} infections, "
          f"peak {int(national.max()):,}/day on day {int(national.argmax())}")
    if args.doubling_upper:
        print(f"doubling time {doubling_time(national, args.doubling_upper):.2f} days")


if __name__ == "__main__":
    main()
