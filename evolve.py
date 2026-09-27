"""Evolutionary search for payloads that evade DefendedAgent, same
reflection-vs-random methodology as the session's other two projects:
compare top vs bottom performers each generation and nudge weights toward
what the top performers had (reflection), or just add noise (random
control), then measure whether reflection actually finds better evasions
faster.
"""
from __future__ import annotations

import random
import statistics

from fixtures import DefendedAgent
from payload import AttackPayload, INSTRUCTION_GOALS, OBFUSCATIONS


def evasion_rate(payload: AttackPayload, defender: DefendedAgent, samples: int = 20) -> float:
    """render() is stochastic (weighted choice over goal phrasing and
    obfuscation), so one render isn't a stable fitness signal — sample it
    several times and take the fraction that got past the defender."""
    hits = 0
    for _ in range(samples):
        rendered = payload.render()
        if defender.evades(payload.surface, rendered):
            hits += 1
    return hits / samples


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
    rng_state = random.getstate()
    random.seed(seed)

    defender = DefendedAgent()
    population = [AttackPayload.random(surface) for _ in range(population_size)]
    history = []

    for gen in range(generations):
        scored = sorted(population, key=lambda p: -evasion_rate(p, defender, samples))
        k = max(2, population_size // 4)
        top, bottom = scored[:k], scored[-k:]

        history.append({
            "generation": gen,
            "best_evasion_rate": evasion_rate(top[0], defender, samples),
            "mean_evasion_rate": statistics.fmean(evasion_rate(p, defender, samples) for p in population),
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

    best = max(population, key=lambda p: evasion_rate(p, defender, samples))
    random.setstate(rng_state)
    return history, best
