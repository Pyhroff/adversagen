#!/usr/bin/env python3
"""Controlled reflection-vs-random red-team experiment.

The experiment compares adaptive reflection-guided mutation with a random
mutation control across attack surfaces. Fitness is estimated from repeated
stochastic renders, with one cached score per individual per generation.

The report includes dispersion, Welch/Mann-Whitney significance tests, and
Cohen's d so statistical significance is not presented without an effect-size
estimate.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics

from evolve import evolve
from payload import SURFACES

REAL_SCANNER_SURFACES = ("tool_poisoning", "memory_injection", "rag_injection")


def run_one(surface: str, seed: int, generations: int, population_size: int, use_reflection: bool, samples: int = 20) -> dict:
    history, best = evolve(surface, generations, population_size, use_reflection, seed, samples=samples)
    target = 0.5
    reached = next((h["generation"] for h in history if h["mean_evasion_rate"] >= target), None)
    return {
        "seed": seed,
        "baseline_mean_evasion": history[0]["mean_evasion_rate"],
        "final_mean_evasion": history[-1]["mean_evasion_rate"],
        "final_best_evasion": history[-1]["best_evasion_rate"],
        "generations_to_50pct_mean_evasion": reached,
        "target_50pct_reached": reached is not None,
    }


def cohen_d(a: list[float], b: list[float]) -> float:
    """Standardized mean difference using pooled sample standard deviation."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    a_mean, b_mean = statistics.fmean(a), statistics.fmean(b)
    a_var, b_var = statistics.variance(a), statistics.variance(b)
    pooled = ((len(a) - 1) * a_var + (len(b) - 1) * b_var) / (len(a) + len(b) - 2)
    if pooled == 0:
        return 0.0 if a_mean == b_mean else float("inf")
    return (a_mean - b_mean) / pooled**0.5


def main():
    parser = argparse.ArgumentParser(description="Reflection vs. random attack-payload mutation, per surface.")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--generations", type=int, default=15)
    parser.add_argument("--population", type=int, default=20)
    parser.add_argument("--out", type=str, default="data/experiment_results.json")
    parser.add_argument(
        "--samples", type=int, default=20,
        help="Renders sampled per fitness evaluation. Lower this with --real-scanners "
             "(each render is a real subprocess call), e.g. 3-5.",
    )
    parser.add_argument("--surfaces", type=str, default=None, help="Comma-separated subset of surfaces to run.")
    parser.add_argument(
        "--real-scanners", action="store_true",
        help="Use the actual mcpaudit/memsentry/ragsentry CLIs for their three mapped surfaces.",
    )
    args = parser.parse_args()

    from scipy import stats as scipy_stats

    if args.real_scanners:
        import evolve as evolve_module
        from real_defender import RealScannerDefender
        evolve_module.DefendedAgent = RealScannerDefender
        surfaces = REAL_SCANNER_SURFACES
    else:
        surfaces = SURFACES

    if args.surfaces:
        requested = set(args.surfaces.split(","))
        surfaces = tuple(s for s in surfaces if s in requested)

    full_report = {}
    print(f"{'Surface':<18}{'Metric':<32}{'Reflection':<20}{'Random':<20}{'p (Welch)':<12}{'p (M-W)':<12}{'Cohen d'}")
    print("-" * 124)

    for surface in surfaces:
        ref_rows = [run_one(surface, s, args.generations, args.population, True, args.samples) for s in range(args.seeds)]
        rnd_rows = [run_one(surface, s, args.generations, args.population, False, args.samples) for s in range(args.seeds)]

        surface_report = {"reflection": ref_rows, "random": rnd_rows, "metrics": {}}

        for metric, label in (
            ("final_best_evasion", "Final best-payload evasion rate"),
            ("generations_to_50pct_mean_evasion", "Generations to 50% mean evasion"),
        ):
            ref_vals = [r[metric] for r in ref_rows if r[metric] is not None]
            rnd_vals = [r[metric] for r in rnd_rows if r[metric] is not None]
            if len(ref_vals) > 0:
                ref_m, ref_s = statistics.fmean(ref_vals), statistics.pstdev(ref_vals)
            else:
                ref_m, ref_s = float('nan'), float('nan')

            if len(rnd_vals) > 0:
                rnd_m, rnd_s = statistics.fmean(rnd_vals), statistics.pstdev(rnd_vals)
            else:
                rnd_m, rnd_s = float('nan'), float('nan')

            if len(ref_vals) > 1 and len(rnd_vals) > 1:
                _, p_t = scipy_stats.ttest_ind(ref_vals, rnd_vals, equal_var=False)
                _, p_u = scipy_stats.mannwhitneyu(ref_vals, rnd_vals, alternative="two-sided")
                d = cohen_d(ref_vals, rnd_vals)
            else:
                p_t, p_u, d = float('nan'), float('nan'), float('nan')

            print(f"{surface:<18}{label:<32}{ref_m:>6.2f} ± {ref_s:<11.2f}{rnd_m:>6.2f} ± {rnd_s:<11.2f}{p_t:<12.4f}{p_u:<12.4f}{d:.3f}")
            surface_report["metrics"][metric] = {
                "reflection_mean": ref_m, "reflection_std": ref_s,
                "random_mean": rnd_m, "random_std": rnd_s,
                "welch_p": p_t, "mannwhitney_p": p_u,
                "cohen_d": d,
                "reflection_n": len(ref_vals),
                "random_n": len(rnd_vals),
            }

        surface_report["target_50pct_reached"] = {
            "reflection": sum(r["target_50pct_reached"] for r in ref_rows),
            "random": sum(r["target_50pct_reached"] for r in rnd_rows),
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
