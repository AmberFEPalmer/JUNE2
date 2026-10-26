"""
Writes one JUNE2 configuration for the EpiBench H3a outbreaks (MetaWards -> JUNE transfer),
derived from configs/config_2021 by text edits (comments and YAML anchors are kept):

- starts 2020-01-01 (a Wednesday, as the MetaWards outbreaks) and runs --days days;
- no interventions: self-isolation, masks and social distancing removed; only the
  disease-course rule that moves hospitalised cases to hospital is kept;
- permanent immunity (level 1.0, no waning), as in MetaWards' SEIR model;
- every transmission rate (beta) multiplied by --beta-scale, the calibrated speed;
- --seed-infections infections seeded in one MSOA (--seed-msoa) on day 0;
- the run's random seed; coordinated-encounter logging and checkpoints off.

    python epibench/make_h3a_config.py --out configs/epibench_h3a/R18_rep1 \
        --beta-scale 1.0 --days 400 --seed-msoa E02000976 --run-seed 1801

Needs only the Python standard library. Paths are relative to the JUNE2 repo root.
"""
import argparse
import os
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

BASE = Path("configs/config_2021")
START = date(2020, 1, 1)

POLICIES = """\
# EpiBench H3a: no interventions. Only the disease-course rule that sends hospitalised
# cases to hospital is kept; the lockdown entry stays dated in 3024 (inert, as upstream).
policies:
  symptom_policies:
    - name: "hospitalize_severe_cases"
      symptoms: ["hospitalised", "intensive_care"]
      override_activities: "*"
      replacement: "medical_facility"
      compliance_rate: 1.0
  temporal_policies:
    - name: "first_national_lockdown"
      start_date: "3024-01-01"
      end_date: "3024-12-31"
      override_activities: ["primary_activity", "leisure"]
      replacement: "residence"
      compliance_rate: 1.0
"""

SEEDS = """\
# EpiBench H3a: {n} infections in MSOA {msoa} on day 0, drawn from anyone living there.
global_parameters:
  default_seed_strength: 1.0
  base_cases_per_capita: 0.0002
infection_seeds:
  - name: "epibench_start_msoa"
    type: "exact"
    date: "{start} 08:00"
    geo_level: "MGU"
    parameters:
      units:
        "{msoa}": {n}
"""


# Replace `pattern` exactly `count` times (fails loudly if the upstream file has changed)
def _sub(text, pattern, repl, count=1, flags=0):
    new, n = re.subn(pattern, repl, text, flags=flags)
    if n != count:
        raise ValueError(f"expected {count} match(es) of {pattern!r}, found {n}; has config_2021 changed?")
    return new


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--beta-scale", required=True, type=float)
    p.add_argument("--days", required=True, type=int)
    p.add_argument("--seed-msoa", required=True)
    p.add_argument("--seed-infections", type=int, default=20)
    p.add_argument("--run-seed", required=True, type=int)
    args = p.parse_args()

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(BASE, out)
    end = START + timedelta(days=args.days)

    sim = (out / "simulation.yaml").read_text()
    sim = _sub(sim, r'start_date : "[^"]*"', f'start_date : "{START}"')
    sim = _sub(sim, r'end_date : "[^"]*"', f'end_date : "{end}"')
    sim = _sub(sim, re.escape(f"{BASE.as_posix()}/"), f"{out.as_posix()}/", count=10)
    sim = _sub(sim, r"random_seed: \d+", f"random_seed: {args.run_seed}")
    sim = _sub(sim, r"save_coordinated_encounters: true", "save_coordinated_encounters: false")
    sim = _sub(sim, r"(checkpoint:\s*\n\s*)enabled: true", r"\1enabled: false")
    (out / "simulation.yaml").write_text(sim)

    disease = (out / "disease.yaml").read_text()
    ### the outcome-rates CSV is found relative to the config folder, which now sits elsewhere
    data_dir = os.path.relpath(Path("data").resolve(), out.resolve())
    disease = _sub(disease, r"file: \.\./\.\./data/", f"file: {data_dir}/")
    disease = _sub(disease, r"(\n\s*)level: 0\.95", r"\g<1>level: 1.0")
    disease = _sub(disease, r"waning_rate: 0\.001", "waning_rate: 0.0")
    (out / "disease.yaml").write_text(disease)

    contacts = (out / "contact_matrices.yaml").read_text()
    scale = lambda m: f"{m[1]}{float(m[2]) * args.beta_scale:.10g}"
    contacts, n_beta = re.subn(r"^(\s*beta:\s*)([0-9.eE+-]+)", scale, contacts, flags=re.M)
    if n_beta == 0:
        raise ValueError("no beta values found in contact_matrices.yaml")
    (out / "contact_matrices.yaml").write_text(contacts)

    if "enabled: false" not in (out / "vaccines.yaml").read_text():
        raise ValueError("vaccines.yaml no longer has vaccination disabled")
    (out / "policies.yaml").write_text(POLICIES)
    (out / "infection_seeds.yaml").write_text(SEEDS.format(n=args.seed_infections, msoa=args.seed_msoa, start=START))
    print(f"{out}: {START} to {end} ({args.days} days), {n_beta} betas x {args.beta_scale:g}, "
          f"{args.seed_infections} seeds in {args.seed_msoa}, random seed {args.run_seed}")


if __name__ == "__main__":
    main()
