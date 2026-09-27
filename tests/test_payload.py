import random

from payload import AttackPayload, SURFACES, INSTRUCTION_GOALS, OBFUSCATIONS


def test_random_payload_has_all_goals_and_obfuscations_weighted():
    random.seed(0)
    for surface in SURFACES:
        p = AttackPayload.random(surface)
        assert set(p.goal_weights.keys()) == set(INSTRUCTION_GOALS[surface])
        assert set(p.obfuscation_weights.keys()) == set(OBFUSCATIONS)
        assert all(w > 0 for w in p.goal_weights.values())
        assert all(w > 0 for w in p.obfuscation_weights.values())


def test_render_produces_a_nonempty_string_for_every_surface():
    random.seed(1)
    for surface in SURFACES:
        p = AttackPayload.random(surface)
        for _ in range(20):
            rendered = p.render()
            assert isinstance(rendered, str) and len(rendered) > 0


def test_mutate_random_keeps_weights_positive():
    random.seed(2)
    p = AttackPayload.random("prompt_injection")
    for _ in range(50):
        p = p.mutate_random(sigma=0.5)
        assert all(w > 0 for w in p.goal_weights.values())
        assert all(w > 0 for w in p.obfuscation_weights.values())


def test_apply_deltas_moves_weights_in_expected_direction_on_average():
    random.seed(3)
    p = AttackPayload.random("tool_poisoning")
    goal = next(iter(p.goal_weights))
    deltas = {goal: 0.5}
    diffs = []
    for _ in range(200):
        child = p.apply_deltas(deltas, {})
        diffs.append(child.goal_weights[goal] - p.goal_weights[goal])
    avg = sum(diffs) / len(diffs)
    assert avg > 0.3, f"expected the targeted goal weight to trend up by ~0.5, got avg delta {avg}"
