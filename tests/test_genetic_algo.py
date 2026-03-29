"""Tests for random_genome() and mutate() in ga/genetic_algo.py.

random_genome() -> dict
    Return a genome with all 7 params randomly sampled within PARAM_RANGES.

mutate(genome) -> dict
    Return a new genome derived from the parent. Each param has RADIATION_INTENSITY
    (25%) chance of being re-rolled within its range. Parent is not modified.

All param values must be integers within [lo, hi] inclusive per PARAM_RANGES.
"""
import random
from ga.genetic_algo import random_genome, mutate, PARAM_RANGES


# ---------------------------------------------------------------------------
# random_genome
# ---------------------------------------------------------------------------

def test_random_genome_has_all_params():
    genome = random_genome()
    assert set(genome.keys()) == set(PARAM_RANGES.keys())


def test_random_genome_no_extra_params():
    genome = random_genome()
    assert len(genome) == len(PARAM_RANGES)


def test_random_genome_values_in_range():
    genome = random_genome()
    for param, (lo, hi) in PARAM_RANGES.items():
        assert lo <= genome[param] <= hi, f"{param}={genome[param]} out of [{lo}, {hi}]"


def test_random_genome_values_are_integers():
    genome = random_genome()
    for param, value in genome.items():
        assert isinstance(value, int), f"{param} is {type(value)}, expected int"


def test_random_genome_repeated_always_valid():
    #run many times to catch any boundary or sampling issues
    for _ in range(200):
        genome = random_genome()
        for param, (lo, hi) in PARAM_RANGES.items():
            assert lo <= genome[param] <= hi


# ---------------------------------------------------------------------------
# mutate — output validity
# ---------------------------------------------------------------------------

def test_mutate_has_all_params():
    parent = random_genome()
    child = mutate(parent)
    assert set(child.keys()) == set(PARAM_RANGES.keys())


def test_mutate_values_in_range():
    parent = random_genome()
    child = mutate(parent)
    for param, (lo, hi) in PARAM_RANGES.items():
        assert lo <= child[param] <= hi, f"{param}={child[param]} out of [{lo}, {hi}]"


def test_mutate_values_are_integers():
    parent = random_genome()
    child = mutate(parent)
    for param, value in child.items():
        assert isinstance(value, int), f"{param} is {type(value)}, expected int"


def test_mutate_repeated_always_valid():
    #run many times to catch any boundary issues after re-rolling
    parent = random_genome()
    for _ in range(200):
        child = mutate(parent)
        for param, (lo, hi) in PARAM_RANGES.items():
            assert lo <= child[param] <= hi


# ---------------------------------------------------------------------------
# mutate: parent isolation
# ---------------------------------------------------------------------------

def test_mutate_does_not_modify_parent():
    parent = random_genome()
    parent_copy = dict(parent)
    mutate(parent)
    assert parent == parent_copy


def test_mutate_returns_new_dict():
    parent = random_genome()
    child = mutate(parent)
    assert child is not parent


# ---------------------------------------------------------------------------
# mutate: boundary genomes
# ---------------------------------------------------------------------------

def test_mutate_from_all_minimums_stays_in_range():
    #parent at lower bound of every param means re-rolls must still land in range
    parent = {param: lo for param, (lo, hi) in PARAM_RANGES.items()}
    for _ in range(50):
        child = mutate(parent)
        for param, (lo, hi) in PARAM_RANGES.items():
            assert lo <= child[param] <= hi


def test_mutate_from_all_maximums_stays_in_range():
    #parent at upper bound of every param means re-rolls must still land in range
    parent = {param: hi for param, (lo, hi) in PARAM_RANGES.items()}
    for _ in range(50):
        child = mutate(parent)
        for param, (lo, hi) in PARAM_RANGES.items():
            assert lo <= child[param] <= hi


# ---------------------------------------------------------------------------
# mutate: mutation firing behavior
# ---------------------------------------------------------------------------

def test_mutate_with_forced_mutation_changes_at_least_one_param():
    #force all params to re-roll by seeding random so random.random() always < 0.25
    #simplest approach: patch RADIATION_INTENSITY to 1.0 via monkeypatch
    parent = {param: lo for param, (lo, hi) in PARAM_RANGES.items()}
    random.seed(42)
    #with seed 42 and 25% rate, statistically very unlikely all 7 miss so run enough times
    changed = False
    for _ in range(20):
        child = mutate(parent)
        if child != parent:
            changed = True
            break
    assert changed, "mutate never changed any param across 20 attempts"


def test_mutate_with_zero_radiation_returns_identical_genome(monkeypatch):
    import ga.genetic_algo as ga_module
    monkeypatch.setattr(ga_module, "RADIATION_INTENSITY", 0.0)
    parent = random_genome()
    child = mutate(parent)
    assert child == parent