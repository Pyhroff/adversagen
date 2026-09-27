# AdversaGen

An adaptive attack-payload generator that evolves evasions against a naive-but-realistic blocklist defense, across the same four attack surfaces your existing static scanners each defend: prompt injection (mcpaudit-adjacent), MCP tool poisoning (mcpaudit), agent memory injection (memsentry), and RAG retrieval injection (ragsentry).

This is the offensive counterpart to that portfolio: those five repos scan for problems; this one actively tries to cause them, adapting its attacks generation over generation instead of firing a static payload list once.

## What's real, what's a stand-in — read this before anything else

- **The defense being attacked (`fixtures.py`) is a deliberately naive, honestly-labeled stand-in**, not your real mcpaudit/memsentry/ragsentry logic: a normalize-then-blocklist check representative of what a first-pass static scanner looks for. It is not connected to your actual private repos — this session doesn't have access to them. See "Pointing this at your real repos" below for how to wire it up for real.
- **The attack payloads and obfuscation techniques (zero-width character insertion, homoglyph substitution, synonym paraphrasing, indirection) are real, documented evasion techniques** used against real content filters — not invented for this project.
- **Every number below was actually run in this session** (30 seeds × 2 conditions × 4 surfaces = 240 evolutionary runs), not estimated or hypothetical.

## The experiment — and an honest, unexpected result

Same reflection-vs-random-mutation methodology as the rest of this portfolio's evolutionary projects, run here across all four surfaces (`python3 experiment.py --seeds 30`):

| Surface | Reflection final evasion | Random final evasion | p (Welch) |
|---|---|---|---|
| Prompt injection | 0.66 ± 0.19 | **0.86 ± 0.11** | <0.0001 |
| Tool poisoning | 0.63 ± 0.24 | **0.91 ± 0.08** | <0.0001 |
| Memory injection | 0.72 ± 0.14 | **0.90 ± 0.09** | <0.0001 |
| RAG injection | 0.64 ± 0.18 | **0.89 ± 0.13** | <0.0001 |

**This is the opposite of what the earlier two projects in this portfolio found** — there, reflection (directed mutation) either matched or beat random mutation. Here, random mutation wins cleanly and consistently, across every single surface, with high significance. That's not a bug to quietly fix and re-run until it says what I expected; it's the actual finding, and it's explainable:

**Diagnosis: reflection collapses population diversity in this landscape, and that's fatal here specifically.** I measured it directly — the standard deviation of one obfuscation weight across the final population is **0.048 under reflection vs. 0.172 under random mutation** (about 3.6x less diverse). Reflection's update rule nudges every child in the same generation toward the *same* direction (the current top-quartile's average weights). That's the right move when fitness is smooth and roughly additive across traits — which is exactly the case in this portfolio's other two projects (an organism's survival odds, or a spam classifier's accuracy, both move roughly monotonically as you turn up any one useful trait). But evading a blocklist is a **combinatorial, interaction-heavy** fitness landscape: a specific goal phrasing only evades when paired with a specific obfuscation, and there's no smooth gradient connecting "somewhat evasive" to "fully evasive" — you either hit a working combination or you don't. Pushing an entire population in one marginal direction *at the cost of diversity* is a bad trade when the win condition is a rare combinatorial hit, and random mutation's preserved diversity keeps sampling enough different combinations to find those hits more often.

That's a genuinely useful, generalizable finding, not a disappointing one: **directed mutation helps when fitness is smooth/additive and hurts when fitness is combinatorial/interaction-heavy, because it trades away the population diversity that combinatorial search actually needs.** Being able to state that boundary condition — and back it up with a measured diversity number, not just a plausible story — is a stronger interview answer than a repeated "reflection wins" result would have been.

## Files

- `payload.py` — the `AttackPayload` genome (goal-phrasing + obfuscation weight vectors), the six obfuscation techniques, and the blocklist-normalization function.
- `fixtures.py` — `VulnerableAgent` (no defense, always complies) and `DefendedAgent` (normalize + blocklist check) for all four surfaces.
- `evolve.py` — the evolutionary loop and the reflection/random mutation operators.
- `experiment.py` — the 30-seed controlled experiment across all four surfaces, with real Welch's t-test / Mann-Whitney U stats via scipy.
- `tests/` — 13 tests covering payload rendering, the fixtures' blocklist coverage (every baseline goal must actually be caught, or the whole experiment measures nothing), obfuscation normalization, and evolution-loop determinism.
- `data/experiment_results.json` — full per-seed results from the bundled run.

## Run it

```bash
pip install -r requirements.txt                                # scipy (only needed for experiment.py's stats)
python3 -m pytest tests/ -q                                   # 13 tests
python3 experiment.py --seeds 30 --generations 15 --population 20   # the full experiment above
```

## Pointing this at your real repos instead of the bundled stand-in

`DefendedAgent.blocks(surface, rendered_text)` in `fixtures.py` is the one seam to replace: swap its body for an actual call into mcpaudit/memsentry/ragsentry's real detection logic (e.g. shell out to mcpaudit's CLI against a fixture tool-description file built from `rendered_text`, and treat a nonzero exit code or a finding in its JSON output as "blocked"). Everything else — the payload genome, the evolutionary loop, the experiment runner, the stats — is already surface-agnostic and doesn't need to change. That's the natural next step if you want a real, not-simulated evasion-rate number against your actual scanners, and it would also slot straight into `agent-security-ci` as an adversarial-testing stage rather than a fixed fixture set.

## Resume line

> Built an adaptive red-teaming tool that evolves attack payloads (prompt injection, MCP tool poisoning, agent memory injection, RAG injection) against a blocklist-based defense across 4 surfaces; ran a 30-seed controlled experiment and found that directed (reflection-guided) mutation underperforms random mutation here by a wide, statistically significant margin (p<0.0001 on all 4 surfaces) — diagnosed the cause as diversity collapse (3.6x lower population variance under directed mutation) in a combinatorial fitness landscape, contrasting with an earlier project where directed mutation won on a smooth/additive one.
