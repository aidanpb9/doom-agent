"""Tests for StateMachine.update() priority/transitions and _get_best_enemy()
in core/execution/state_machine.py.

update() evaluates conditions from highest to lowest priority each tick:
    STUCK > COMBAT > SCAN > RECOVER > TRAVERSE

_get_best_enemy(gamestate) returns the most centered in-range enemy with clear
LOS, or (None, 0.0) when no valid target exists.
"""
from unittest.mock import MagicMock
from core.execution.state_machine import StateMachine, State
from core.execution.game_state import GameState, EnemyObject
from core.execution.action_decoder import ActionDecoder
from config.constants import (
    HEALTH_THRESHOLD, AMMO_THRESHOLD,
    HEALTH_KEYWORDS, AMMO_KEYWORDS,
    COMBAT_MAX_RANGE, COMBAT_HOLD_TICKS, TICK,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sm():
    """StateMachine with a fully mocked PathTracker and no blocking geometry."""
    mock_pt = MagicMock()
    mock_pt.is_stuck = False
    mock_pt.has_loot_node.return_value = False
    mock_pt.get_next_move.return_value = ActionDecoder.null_action()
    sm = StateMachine(mock_pt, blocking_segments=[])
    return sm, mock_pt


def make_gs(**kwargs):
    """GameState with safe defaults (healthy, no threats, 640-wide screen)."""
    defaults = dict(
        health=100, armor=50, ammo=50,
        enemies_visible=[], loots_visible=[],
        pos_x=0.0, pos_y=0.0, angle=0.0,
        enemies_killed=0,
        is_dmg_taken_since_last_step=False,
        screen_width=640.0,
    )
    defaults.update(kwargs)
    return GameState(**defaults)


def make_enemy(pos_x=100.0, pos_y=0.0, screen_x=320.0):
    """Enemy within combat range, centered on screen by default."""
    return EnemyObject(name="zombie", pos_x=pos_x, pos_y=pos_y, screen_x=screen_x, screen_y=240.0)


# ---------------------------------------------------------------------------
# update(): priority and transitions
# ---------------------------------------------------------------------------

def test_stuck_fires_when_path_tracker_is_stuck():
    sm, mock_pt = make_sm()
    mock_pt.is_stuck = True
    sm.update(make_gs())
    assert sm.last_state == State.STUCK


def test_stuck_overrides_combat():
    #is_stuck should trump enemy presence since the agent can't fight or navigate
    #effectively while wedged against geometry
    sm, mock_pt = make_sm()
    mock_pt.is_stuck = True
    sm.update(make_gs(ammo=50, enemies_visible=[make_enemy()]))
    assert sm.last_state == State.STUCK


def test_combat_fires_when_enemies_visible_and_ammo_positive():
    sm, mock_pt = make_sm()
    #scan_cooldown=999 survives the per-tick decrement (max(0,999-1)=998>0) so
    #"not self.scan_cooldown" stays False and random SCAN never fires before COMBAT
    sm.scan_cooldown = 999
    sm.update(make_gs(ammo=50, enemies_visible=[make_enemy()]))
    assert sm.last_state == State.COMBAT


def test_combat_does_not_fire_when_ammo_zero():
    #combat condition is "(hold or enemies_visible) and ammo > 0", so ammo=0
    #must prevent entry even when an enemy is visible
    sm, mock_pt = make_sm()
    sm.scan_cooldown = 999
    sm.update(make_gs(ammo=0, enemies_visible=[make_enemy()]))
    assert sm.last_state != State.COMBAT


def test_combat_hold_keeps_combat_branch_active():
    #after an enemy leaves FOV, combat_hold keeps the combat branch alive so the
    #agent doesn't immediately break off to recover. health=0 ensures RECOVER would
    #fire if combat hold weren't blocking it, proving hold is what's suppressing it.
    #we check set_goal_by_type rather than last_state because _combat() with no
    #valid target returns get_next_move() without updating last_state
    sm, mock_pt = make_sm()
    sm.combat_hold = COMBAT_HOLD_TICKS #still > 0 after one TICK decrement
    mock_pt.has_loot_node.return_value = True
    sm.update(make_gs(ammo=10, health=0, enemies_visible=[]))
    mock_pt.set_goal_by_type.assert_not_called()


def test_combat_exits_when_hold_expires_and_no_enemies():
    #combat_hold=TICK -> max(0, TICK-TICK)=0, hold fully expires this tick,
    #allowing the agent to fall through to RECOVER
    sm, mock_pt = make_sm()
    sm.combat_hold = TICK
    sm.scan_cooldown = 999
    mock_pt.has_loot_node.return_value = True
    sm.update(make_gs(ammo=10, health=0, enemies_visible=[]))
    assert sm.last_state == State.RECOVER


def test_scan_fires_when_damage_taken_and_cooldown_zero():
    #cooldown=0 -> "not self.scan_cooldown" is True; is_dmg_taken satisfies the
    #second OR condition deterministically without relying on the random scan chance
    sm, mock_pt = make_sm()
    sm.scan_cooldown = 0
    sm.update(make_gs(is_dmg_taken_since_last_step=True))
    assert sm.last_state == State.SCAN


def test_scan_continues_when_already_scanning():
    #update() checks "if self.last_state == State.SCAN" before the cooldown/dmg
    #gate so an in-progress scan always continues regardless of those conditions.
    #scan_last_angle=45, angle=0 -> deg=45 added to scan_total_deg=90 -> 135,
    #not yet past 360 so the scan keeps going
    sm, mock_pt = make_sm()
    sm.last_state = State.SCAN
    sm.scan_last_angle = 45.0
    sm.scan_total_deg = 90.0
    sm.update(make_gs(angle=0.0))
    assert sm.last_state == State.SCAN


def test_recover_fires_when_health_below_threshold_and_loot_known():
    #side_effect returns True only for HEALTH_KEYWORDS so only the health branch
    #fires; using side_effect rather than return_value=True avoids accidentally
    #satisfying ammo/armor branches and masking a wrong-branch bug
    sm, mock_pt = make_sm()
    sm.scan_cooldown = 999
    mock_pt.has_loot_node.side_effect = lambda kw: kw == HEALTH_KEYWORDS
    sm.update(make_gs(health=HEALTH_THRESHOLD - 1))
    assert sm.last_state == State.RECOVER


def test_recover_fires_when_ammo_below_threshold_and_loot_known():
    #health=100 and armor=50 (defaults) are above their thresholds so only the
    #ammo branch can trigger RECOVER here
    sm, mock_pt = make_sm()
    sm.scan_cooldown = 999
    mock_pt.has_loot_node.side_effect = lambda kw: kw == AMMO_KEYWORDS
    sm.update(make_gs(ammo=AMMO_THRESHOLD - 1))
    assert sm.last_state == State.RECOVER


def test_recover_does_not_fire_when_loot_not_known():
    #all three recover branches require has_loot_node() to return True for the
    #matching keyword set; without a known loot node the agent falls through to TRAVERSE
    sm, mock_pt = make_sm()
    sm.scan_cooldown = 999
    mock_pt.has_loot_node.return_value = False
    sm.update(make_gs(health=0, ammo=0, armor=0))
    assert sm.last_state != State.RECOVER


def test_scan_fires_above_recover_when_both_conditions_met():
    #SCAN is checked before RECOVER in the priority chain, so taking damage while
    #low on health should trigger a scan rather than immediately going for loot
    sm, mock_pt = make_sm()
    sm.scan_cooldown = 0
    mock_pt.has_loot_node.return_value = True
    sm.update(make_gs(health=HEALTH_THRESHOLD - 1, is_dmg_taken_since_last_step=True))
    assert sm.last_state == State.SCAN


def test_traverse_is_default_when_nothing_else_fires():
    sm, mock_pt = make_sm()
    sm.scan_cooldown = 999
    sm.update(make_gs()) #full health, no enemies, no damage
    assert sm.last_state == State.TRAVERSE


# ---------------------------------------------------------------------------
# _get_best_enemy
# ---------------------------------------------------------------------------

def test_get_best_enemy_returns_none_when_no_enemies():
    sm, _ = make_sm()
    enemy, offset = sm._get_best_enemy(make_gs(enemies_visible=[]))
    assert enemy is None
    assert offset == 0.0


def test_get_best_enemy_ignores_enemies_beyond_max_range():
    #agent is at (0,0), enemy at (COMBAT_MAX_RANGE+1, 0) -> distance just exceeds limit
    sm, _ = make_sm()
    far_enemy = make_enemy(pos_x=COMBAT_MAX_RANGE + 1, pos_y=0.0)
    enemy, _ = sm._get_best_enemy(make_gs(enemies_visible=[far_enemy]))
    assert enemy is None


def test_get_best_enemy_ignores_enemies_with_no_clear_los(monkeypatch):
    #patch the bound name in state_machine's namespace (after "from core.utils import")
    #so the check inside _get_best_enemy always reports blocked
    import core.execution.state_machine as sm_module
    monkeypatch.setattr(sm_module, "has_clear_world_line", lambda *args: False)
    sm, _ = make_sm()
    enemy, _ = sm._get_best_enemy(make_gs(enemies_visible=[make_enemy()]))
    assert enemy is None


def test_get_best_enemy_returns_most_centered_enemy():
    #screen_width=640, center=320
    #centered: screen_x=320 -> abs offset = 0.0
    #off_center: screen_x=100 -> abs offset = (100-320)/640 ≈ 0.34
    sm, _ = make_sm()
    centered = make_enemy(pos_x=100.0, pos_y=0.0, screen_x=320.0)
    off_center = make_enemy(pos_x=50.0, pos_y=50.0, screen_x=100.0)
    enemy, _ = sm._get_best_enemy(make_gs(enemies_visible=[off_center, centered]))
    assert enemy is centered