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