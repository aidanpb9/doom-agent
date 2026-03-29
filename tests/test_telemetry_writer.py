"""Tests for TelemetryWriter in core/execution/telemetry_writer.py.

All tests write to a tmp_path (pytest fixture) so no real output/ dirs are created.
finalize_episode() is always called with a stats dict; the map render is expected
to fail silently in tests (no map JSON on disk), which is already handled by the
try/except in finalize_episode().
"""
import csv
import json
from core.execution.telemetry_writer import TelemetryWriter
from core.execution.game_state import GameState


REQUIRED_TIER1_FIELDS = {
    "episode_id", "level_id", "seed", "end_reason", "ticks",
    "health", "armor", "ammo", "enemies_killed", "waypoints_reached",
    "stuck_events", "damage_taken_total", "ammo_used", "fitness",
}

TIER2_COLUMNS = ["tick", "action", "sm_state", "pos_x", "pos_y"]


def make_stats(**kwargs) -> dict:
    defaults = dict(
        end_reason="timeout", ticks=100, health=50, armor=10,
        ammo=30, enemies_killed=2, waypoints_reached=5, fitness=1234.0,
    )
    defaults.update(kwargs)
    return defaults


def make_gs(**kwargs) -> GameState:
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


NULL_ACTION = [0, 0, 0, 0, 0, 0]  #matches ACTION_COUNT=6, no buttons pressed
SM_TRAVERSE = 5


def run_episode(tw: TelemetryWriter, tmp_path, episode_id=1,
                episode_prefix="", genome=None, steps=None, stats=None):
    """Start, optionally record steps, then finalize. Return the Tier 1 summary dict."""
    tw.start_episode("E1M1", episode_id, seed=0, genome=genome,
                     episode_prefix=episode_prefix)
    for gs, action, sm_state in (steps or []):
        tw.record_step(gs, action, sm_state)
    tw.finalize_episode(stats or make_stats())
    return json.loads((tmp_path / f"{(episode_prefix + '_' if episode_prefix else '')}ep_{episode_id:04d}_summary.json").read_text())


# ---------------------------------------------------------------------------
# Tier 1 summary
# ---------------------------------------------------------------------------

def test_tier1_contains_all_required_fields(tmp_path):
    tw = TelemetryWriter(output_dir=str(tmp_path))
    summary = run_episode(tw, tmp_path)
    assert REQUIRED_TIER1_FIELDS.issubset(summary.keys())


def test_fitness_value_matches_stats_input(tmp_path):
    tw = TelemetryWriter(output_dir=str(tmp_path))
    summary = run_episode(tw, tmp_path, stats=make_stats(fitness=9999.0))
    assert summary["fitness"] == 9999.0


def test_genome_embedded_in_summary_when_provided(tmp_path):
    genome = {"health_threshold": 60, "ammo_threshold": 20}
    tw = TelemetryWriter(output_dir=str(tmp_path))
    summary = run_episode(tw, tmp_path, genome=genome)
    assert "genome" in summary
    assert summary["genome"] == genome


def test_genome_omitted_from_summary_in_run_mode(tmp_path):
    #genome=None (default) means run mode so no genome key should appear
    tw = TelemetryWriter(output_dir=str(tmp_path))
    summary = run_episode(tw, tmp_path, genome=None)
    assert "genome" not in summary


# ---------------------------------------------------------------------------
# Tier 2 CSV
# ---------------------------------------------------------------------------

def test_tier2_has_correct_column_headers(tmp_path):
    tw = TelemetryWriter(output_dir=str(tmp_path))
    tw.start_episode("E1M1", episode_id=1, seed=0)
    tw.finalize_episode(make_stats())
    with open(tmp_path / "ep_0001_actions.csv", newline="") as f:
        header = next(csv.reader(f))
    assert header == TIER2_COLUMNS


# ---------------------------------------------------------------------------
# Derived stats
# ---------------------------------------------------------------------------

def test_ammo_used_computed_correctly(tmp_path):
    #ammo_start captured on first record_step tick; ammo_used = start - end
    tw = TelemetryWriter(output_dir=str(tmp_path))
    steps = [(make_gs(ammo=50), NULL_ACTION, SM_TRAVERSE)]  #ammo_start = 50
    summary = run_episode(tw, tmp_path, steps=steps, stats=make_stats(ammo=30))
    assert summary["ammo_used"] == 20


def test_ammo_used_clamped_to_zero_when_ammo_increases(tmp_path):
    #agent picks up ammo: ammo_start=30, ammo_end=50 -> max(0, 30-50) = 0
    tw = TelemetryWriter(output_dir=str(tmp_path))
    steps = [(make_gs(ammo=30), NULL_ACTION, SM_TRAVERSE)]  #ammo_start = 30
    summary = run_episode(tw, tmp_path, steps=steps, stats=make_stats(ammo=50))
    assert summary["ammo_used"] == 0


def test_damage_taken_ignores_healing(tmp_path):
    #step 1: health 100->50, damage=50
    #step 2: health 50->80 (medikit), max(0, 50-80)=0, damage not subtracted
    #total damage_taken_total should be 50, not 20
    tw = TelemetryWriter(output_dir=str(tmp_path))
    steps = [
        (make_gs(health=50), NULL_ACTION, SM_TRAVERSE), #takes 50 damage
        (make_gs(health=80), NULL_ACTION, SM_TRAVERSE), #heals, must not subtract
    ]
    summary = run_episode(tw, tmp_path, steps=steps)
    assert summary["damage_taken_total"] == 50


# ---------------------------------------------------------------------------
# Output filenames
# ---------------------------------------------------------------------------

def test_episode_id_reflected_in_output_filenames(tmp_path):
    tw = TelemetryWriter(output_dir=str(tmp_path))
    tw.start_episode("E1M1", episode_id=42, seed=0)
    tw.finalize_episode(make_stats())
    assert (tmp_path / "ep_0042_summary.json").exists()
    assert (tmp_path / "ep_0042_actions.csv").exists()


def test_episode_prefix_reflected_in_output_filenames(tmp_path):
    #episode_prefix="elite" should produce elite_ep_0042_summary.json
    #this is how evolve mode distinguishes elite vs challenger files
    tw = TelemetryWriter(output_dir=str(tmp_path))
    tw.start_episode("E1M1", episode_id=42, seed=0, episode_prefix="elite")
    tw.finalize_episode(make_stats())
    assert (tmp_path / "elite_ep_0042_summary.json").exists()
    assert (tmp_path / "elite_ep_0042_actions.csv").exists()