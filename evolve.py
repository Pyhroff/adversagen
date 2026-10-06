"""Evolutionary search for payloads that evade a defender.

Fitness is stochastic because payload rendering samples from a genome's
weight distributions. Each payload is therefore evaluated once per
generation and its sampled score is reused for selection and history.
This keeps the evolutionary decision and reported metric on the same
measurement instead of re-sampling the same individual several times.
"""
from __future__ import annotations

import random
import statistics

from fixtures import DefendedAgent
from payload import AttackPayload, INSTRUCTION_GOALS, OBFUSCATIONS


def evasion_rate(payload: AttackPayload, defender: DefendedAgent, samples: int = 20) -> float:
    """Estimate evasion probability from repeated stochastic renders."""
    if samples <= 0:
        raise ValueError("samples must be > 0")
    hits = 0
    for _ in range(samples):
        rendered = payload.render()
        if defender.evades(payload.surface, rendered):
            hits += 1
    return hits / samples


def score_population(
    population: list[AttackPayload],
    defender: DefendedAgent,
    samples: int,
) -> list[tuple[AttackPayload, float]]:
    """Score each individual exactly once and return it sorted by fitness."""
    scored = [(payload, evasion_rate(payload, defender, samples)) for payload in population]
    return sorted(scored, key=lambda item: item[1], reverse=True)


def reflect(surface: str, top: list, bottom: list, learning_rate: float = 0.6) -> tuple[dict, dict]:
    goal_deltas = {}
    for goal in INSTRUCTION_GOALS[surface]:
        top_avg = statistics.fmean(p.goal_weights[goal] for p in top)
        bottom_avg = statistics.fmean(p.goal_weights[goal] for p in bottom)
        goal_deltas[goal] = (top_avg - bottom_avg) * learning_rate

    obf_deltas = {}
    for obf in OBFUSCATIONS:
        top_avg = statistics.fmean(p.obfuscation_weights[obf] for p in top)
        bottom_avg = statistics.fmean(p.obfuscation_weights[obf] for p in bottom)
        obf_deltas[obf] = (top_avg - bottom_avg) * learning_rate

    return goal_deltas, obf_deltas


def evolve(surface: str, generations: int, population_size: int, use_reflection: bool, seed: int, samples: int = 20):
    if generations <= 0:
        raise ValueError("generations must be > 0")
    if population_size < 4:
        raise ValueError("population_size must be >= 4")
    if samples <= 0:
        raise ValueError("samples must be > 0")

    rng_state = random.getstate()
    random.seed(seed)

    defender = DefendedAgent()
    population = [AttackPayload.random(surface) for _ in range(population_size)]
    history = []

    try:
        for gen in range(generations):
            scored = score_population(population, defender, samples)
            k = max(2, population_size // 4)
            top_scored, bottom_scored = scored[:k], scored[-k:]
            top = [payload for payload, _ in top_scored]
            bottom = [payload for payload, _ in bottom_scored]
            scores = [score for _, score in scored]

            history.append({
                "generation": gen,
                "best_evasion_rate": top_scored[0][1],
                "mean_evasion_rate": statistics.fmean(scores),
            })

            next_population = list(top)
            while len(next_population) < population_size:
                parent = random.choice(top)
                if use_reflection:
                    goal_deltas, obf_deltas = reflect(surface, top, bottom)
                    child = parent.apply_deltas(goal_deltas, obf_deltas)
                else:
                    child = parent.mutate_random(sigma=0.3)
                next_population.append(child)
            population = next_population

        final_scored = score_population(population, defender, samples)
        best = final_scored[0][0]
        return history, best
    finally:
        random.setstate(rng_state)
