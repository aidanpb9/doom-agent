"""Tests for compute_fitness() in ga/genetic_algo.py.

compute_fitness(stats: dict) -> float

Two branches:
  - Completion:     stats["finish_level"] = True  → base 1000 + speed + health + armor + ammo
  - Non-completion: stats["finish_level"] = False → kills * 5 + waypoints * 10

All tests use known inputs with hand-calculated expected values.
"""
import pytest
from ga.genetic_algo import compute_fitness


# ---------------------------------------------------------------------------
# Completion branch
# ---------------------------------------------------------------------------

def test_completion_correct_value():
    #ticks=2100 → speed bonus = 500 * (1 - 2100/4200) = 250
    #health=80 → 160, armor=50 → 50, ammo=100 → 50
    #expected = 1000 + 250 + 160 + 50 + 50 = 1510.0
    stats = {"finish_level": True, "ticks": 2100, "health": 80, "armor": 50, "ammo": 100}
    assert compute_fitness(stats) == pytest.approx(1510.0)


def test_completion_speed_bonus_negative_for_slow_run():
    #ticks=8400 → speed bonus = 500*(1 - 8400/4200) = 500*(-1) = -500
    #expected = 1000 - 500 = 500.0
    stats = {"finish_level": True, "ticks": 8400, "health": 0, "armor": 0, "ammo": 0}
    assert compute_fitness(stats) == pytest.approx(500.0)


def test_completion_speed_bonus_zero_at_4200_ticks():
    #ticks=4200 → speed bonus = 500*(1 - 4200/4200) = 0
    #expected = 1000 + 0 + 0 + 0 + 0 = 1000.0
    stats = {"finish_level": True, "ticks": 4200, "health": 0, "armor": 0, "ammo": 0}
    assert compute_fitness(stats) == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# Non-completion branch
# ---------------------------------------------------------------------------

def test_non_completion_weights():
    #enemies_killed=10 → 50, waypoints_reached=5 → 50
    #expected = 100.0
    stats = {"finish_level": False, "enemies_killed": 10, "waypoints_reached": 5}
    assert compute_fitness(stats) == 100.0


def test_non_completion_when_health_nonzero():
    #finish_level=False should use non-completion branch regardless of health
    #enemies_killed=3 → 15, waypoints_reached=2 → 20, expected = 35.0
    stats = {"finish_level": False, "health": 100, "enemies_killed": 3, "waypoints_reached": 2}
    assert compute_fitness(stats) == 35.0


def test_non_completion_all_zeros():
    #no kills, no waypoints → fitness should be 0.0, not crash
    stats = {"finish_level": False, "enemies_killed": 0, "waypoints_reached": 0}
    assert compute_fitness(stats) == 0.0


def test_finish_level_missing_falls_to_non_completion():
    #finish_level absent → stats.get() returns None (falsy) → non-completion branch
    stats = {"enemies_killed": 4, "waypoints_reached": 3}
    assert compute_fitness(stats) == 50.0  #4*5 + 3*10


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

def test_result_rounded_to_2_decimal_places():
    #ticks=1000 → speed bonus = 500*(1 - 1000/4200) = 380.952380...
    #ammo=1 → 0.5, raw = 1381.452380... → should round to 1381.45
    stats = {"finish_level": True, "ticks": 1000, "health": 0, "armor": 0, "ammo": 1}
    result = compute_fitness(stats)
    assert result == round(result, 2)