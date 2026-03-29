"""Tests for compute_fitness() in ga/genetic_algo.py.

compute_fitness(stats: dict) -> float

Two branches:
  - Completion:     stats["finish_level"] = True  -> base 5000 + speed + health + armor + ammo
  - Non-completion: stats["finish_level"] = False -> kills * 5 + waypoints * 10

Base is 5000 so that even a worst-case slow completion (5000 - 1000 speed penalty = 4000)
beats the best realistic non-completion on any level.

All tests use known inputs with hand-calculated expected values.
"""
import pytest
from ga.genetic_algo import compute_fitness


# ---------------------------------------------------------------------------
# Completion branch
# ---------------------------------------------------------------------------

def test_completion_correct_value():
    #ticks=2100 -> speed bonus = 500 * (1 - 2100/4200) = 250
    #health=80 -> 160, armor=50 -> 50, ammo=100 -> 50
    #expected = 5000 + 250 + 160 + 50 + 50 = 5510.0
    stats = {"finish_level": True, "ticks": 2100, "health": 80, "armor": 50, "ammo": 100}
    assert compute_fitness(stats) == pytest.approx(5510.0)


def test_completion_speed_bonus_negative_for_slow_run():
    #ticks=8400 -> speed bonus = 500*(1 - 8400/4200) = 500*(-1) = -500
    #expected = 5000 - 500 = 4500.0
    stats = {"finish_level": True, "ticks": 8400, "health": 0, "armor": 0, "ammo": 0}
    assert compute_fitness(stats) == pytest.approx(4500.0)


def test_completion_speed_bonus_zero_at_4200_ticks():
    #ticks=4200 -> speed bonus = 500*(1 - 4200/4200) = 0
    #expected = 5000 + 0 + 0 + 0 + 0 = 5000.0
    stats = {"finish_level": True, "ticks": 4200, "health": 0, "armor": 0, "ammo": 0}
    assert compute_fitness(stats) == pytest.approx(5000.0)


# ---------------------------------------------------------------------------
# Non-completion branch
# ---------------------------------------------------------------------------

def test_non_completion_weights():
    #enemies_killed=10 -> 50, waypoints_reached=5 -> 50
    #expected = 100.0
    stats = {"finish_level": False, "enemies_killed": 10, "waypoints_reached": 5}
    assert compute_fitness(stats) == 100.0


def test_non_completion_when_health_nonzero():
    #finish_level=False should use non-completion branch regardless of health
    #enemies_killed=3 -> 15, waypoints_reached=2 -> 20, expected = 35.0
    stats = {"finish_level": False, "health": 100, "enemies_killed": 3, "waypoints_reached": 2}
    assert compute_fitness(stats) == 35.0


def test_non_completion_all_zeros():
    #no kills, no waypoints -> fitness should be 0.0, not crash
    stats = {"finish_level": False, "enemies_killed": 0, "waypoints_reached": 0}
    assert compute_fitness(stats) == 0.0


def test_finish_level_missing_falls_to_non_completion():
    #finish_level absent -> stats.get() returns None (falsy) -> non-completion branch
    stats = {"enemies_killed": 4, "waypoints_reached": 3}
    assert compute_fitness(stats) == 50.0  #4*5 + 3*10


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

def test_result_rounded_to_2_decimal_places():
    #ticks=1000 -> speed bonus = 500*(1 - 1000/4200) = 380.952380...
    #ammo=1 -> 0.5, raw = 5381.452380... -> rounded to 2dp
    stats = {"finish_level": True, "ticks": 1000, "health": 0, "armor": 0, "ammo": 1}
    result = compute_fitness(stats)
    assert result == round(result, 2)


# ---------------------------------------------------------------------------
# Weight sanity: better performance must score higher
# ---------------------------------------------------------------------------

def test_completion_beats_non_completion():
    #finishing at all should score higher than the best possible non-completion
    finished = {"finish_level": True, "ticks": 4200, "health": 0, "armor": 0, "ammo": 0}
    not_finished = {"finish_level": False, "enemies_killed": 100, "waypoints_reached": 100}
    assert compute_fitness(finished) > compute_fitness(not_finished)


def test_faster_completion_scores_higher():
    fast = {"finish_level": True, "ticks": 1000, "health": 0, "armor": 0, "ammo": 0}
    slow = {"finish_level": True, "ticks": 4000, "health": 0, "armor": 0, "ammo": 0}
    assert compute_fitness(fast) > compute_fitness(slow)


def test_more_health_scores_higher_on_completion():
    full_health = {"finish_level": True, "ticks": 2100, "health": 100, "armor": 0, "ammo": 0}
    no_health   = {"finish_level": True, "ticks": 2100, "health": 0,   "armor": 0, "ammo": 0}
    assert compute_fitness(full_health) > compute_fitness(no_health)


def test_more_kills_scores_higher_on_non_completion():
    many_kills = {"finish_level": False, "enemies_killed": 10, "waypoints_reached": 0}
    few_kills  = {"finish_level": False, "enemies_killed": 1,  "waypoints_reached": 0}
    assert compute_fitness(many_kills) > compute_fitness(few_kills)


def test_more_waypoints_scores_higher_on_non_completion():
    many_wp = {"finish_level": False, "enemies_killed": 0, "waypoints_reached": 10}
    few_wp  = {"finish_level": False, "enemies_killed": 0, "waypoints_reached": 1}
    assert compute_fitness(many_wp) > compute_fitness(few_wp)