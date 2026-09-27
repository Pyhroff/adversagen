#!/usr/bin/env python3
"""Controlled experiment: does reflection-guided attack mutation actually
find better evasions faster than random mutation, across all four attack
surfaces? Same 30-seed methodology (Welch's t-test, Mann-Whitney U via
scipy) as the session's other two projects, applied here to red-teaming
instead of ecosystems or spam filters.

Usage:
    python3 experiment.py --seeds 30 --generations 15 --population 20
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

from evolve import evolve
from fixtures import DefendedAgent
from payload import SURFACES

REAL_SCANNER_SURFACES = ("tool_poisoning", "memory_injection", "rag_injection")


def run_one(surface: str, seed: int, generations: int, population_size: int, use_reflection: bool, samples: int = 20) -> dict:
    history, best = evolve(surface, generations, population_size, use_reflection, seed, samples=samples)
    target = 0.5
    gens_to_target = next((h["generation"] for h in history if h["mean_evasion_rate"] >= target), generations)
    return {
        "seed": seed,
        "baseline_mean_evasion": history[0]["mean_evasion_rate"],
        "final_mean_evasion": history[-1]["mean_evasion_rate"],
        "final_best_evasion": history[-1]["best_evasion_rate"],
        "generations_to_50pct_mean_evasion": gens_to_target,
    }


def main():
    parser = argparse.ArgumentParser(description="Reflection vs. random attack-payload mutation, per surface.")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--generations", type=int, default=15)
    parser.add_argument("--population", type=int, default=20)
    parser.add_argument("--out", type=str, default="data/experiment_results.json")
    parser.add_argument(
        "--samples", type=int, default=20,
        help="Renders sampled per fitness evaluation. Lower this a lot with --real-scanners "
             "(each render is a real subprocess call) -- e.g. 3-5, not the default 20.",
    )
    parser.add_argument(
        "--surfaces", type=str, default=None,
        help="Comma-separated subset of surfaces to run (default: all applicable ones).",
    )
    parser.add_argument(
        "--real-scanners", action="store_true",
        help=(
            "Use the actual mcpaudit/memsentry/ragsentry CLIs (real_defender.RealScannerDefender) "
            "instead of the naive blocklist stand-in. Each call is a real subprocess -- 2-3 orders "
            "of magnitude slower than the in-memory check -- so this only runs the 3 surfaces that "
            "have a real scanner mapping (prompt_injection has none, see real_defender.py), and you "
            "should pass much smaller --seeds/--generations/--population than the bundled default."
        ),
    )
    args = parser.parse_args()

    from scipy import stats as scipy_stats

    if args.real_scanners:
        import evolve as evolve_module
        from real_defender import RealScannerDefender
        evolve_module.DefendedAgent = RealScannerDefender  # evolve.evolve() constructs DefendedAgent() with no args
        surfaces = REAL_SCANNER_SURFACES
    else:
        surfaces = SURFACES

    if args.surfaces:
        requested = set(args.surfaces.split(","))
        surfaces = tuple(s for s in surfaces if s in requested)

    full_report = {}
    print(f"{'Surface':<18}{'Metric':<32}{'Reflection':<20}{'Random':<20}{'p (Welch)':<12}p (M-W)")
    print("-" * 112)

    for surface in surfaces:
        ref_rows = [run_one(surface, s, args.generations, args.population, True, args.samples) for s in range(args.seeds)]
        rnd_rows = [run_one(surface, s, args.generations, args.population, False, args.samples) for s in range(args.seeds)]

        surface_report = {"reflection": ref_rows, "random": rnd_rows, "metrics": {}}

        for metric, label in (
            ("final_best_evasion", "Final best-payload evasion rate"),
            ("generations_to_50pct_mean_evasion", "Generations to 50% mean evasion"),
        ):
            ref_vals = [r[metric] for r in ref_rows]
            rnd_vals = [r[metric] for r in rnd_rows]
            ref_m, ref_s = statistics.fmean(ref_vals), statistics.pstdev(ref_vals)
            rnd_m, rnd_s = statistics.fmean(rnd_vals), statistics.pstdev(rnd_vals)
            t_stat, p_t = scipy_stats.ttest_ind(ref_vals, rnd_vals, equal_var=False)
            u_stat, p_u = scipy_stats.mannwhitneyu(ref_vals, rnd_vals, alternative="two-sided")
            print(f"{surface:<18}{label:<32}{ref_m:>6.2f} ± {ref_s:<11.2f}{rnd_m:>6.2f} ± {rnd_s:<11.2f}{p_t:<12.4f}{p_u:.4f}")
            surface_report["metrics"][metric] = {
                "reflection_mean": ref_m, "reflection_std": ref_s,
                "random_mean": rnd_m, "random_std": rnd_s,
                "welch_p": p_t, "mannwhitney_p": p_u,
            }
        print()
        full_report[surface] = surface_report

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)
        existing.update(full_report)
        full_report = existing
    with open(out_path, "w") as f:
        json.dump(full_report, f, indent=2)
    print(f"Full results written to: {out_path}")


if __name__ == "__main__":
    main()
