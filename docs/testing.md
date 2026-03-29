core/execution/state_machine.py — priority and transitions

 STUCK fires when path_tracker.is_stuck = True, overrides everything
 COMBAT fires when enemies visible and ammo > 0
 COMBAT does not fire when ammo = 0
 COMBAT stays active during combat_hold countdown
 COMBAT exits when combat_hold expires and no enemies
 SCAN fires when damage taken and cooldown = 0
 SCAN continues when last_state = SCAN (sticky until complete)
 RECOVER fires when health below threshold and health loot known
 RECOVER fires when ammo below threshold and ammo loot known
 RECOVER does not fire when loot not known
 SCAN fires above RECOVER when both conditions met
 TRAVERSE is default when nothing else fires


core/execution/state_machine.py — _get_best_enemy

 Ignores enemies beyond COMBAT_MAX_RANGE
 Ignores enemies with no clear LOS
 Returns most centered enemy when multiple visible
 Returns None when no valid enemies


core/execution/telemetry_writer.py

 Tier 1 summary contains all required fields
 Tier 2 CSV has correct column headers
 fitness value in summary matches stats input
 genome embedded in summary when provided
 genome omitted from summary in run mode
 ammo_used computed correctly (start minus end)
 episode ID reflected in output filenames


Integration (local only, skip in CI)

 Full episode runs without crashing
 run_episode() returns stats dict with all required keys
 Tier 1 and Tier 2 files are created on disk
 Map SVG is generated

19. Set up GitHub Actions pipeline that runs tests automatically on every push
20. Add a badge to README