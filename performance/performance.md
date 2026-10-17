## Regression
Determined that episodes have deterministic hashes.
Saved that result into performance/output/golden/
All new benchmarks test against this.

## Optimizations

### path_tracker
Moved the cheap checks in _place_node() before expensive checks.
Added bounds to segments to cut down on searching.

### reusing vizdoom engine for ga multi-episodes
Instead of closing and opening the engine each episode in the ga,
reset the episode without closing the engine.
This gave a nice speedup for the ga only.

### lru_cache on utils.load_blocking_segments_from_wad()
No significant speedup: micro-benchmarked at 150x for many calls,
but at one call per episode, the speedup to the episode is negligible.
Implemented lru_cache on the function anyways.

### telemetry file flushes
Only 1% episode speedup for removing file flushes according to Amdahl's.
Not implemented, not worth the log safety.

## Benchmarks
Restarted pc and ran a warmup run, then alternated branches to get even benchmarks, 3 each.
Before avg median episode seconds: 12.53820346
Before avg stddev