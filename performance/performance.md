## Regression
Determined that episodes have deterministic hashes.
Saved that result into performance/output/golden/
All new benchmarks test against this.

## Benchmark Process
Restart PC.
Run an entire warmup benchmark.

## Before optimizations
For 5 runs (excluded warmup):
Time median: 12.47853938299997
Time stddev: 0.18186761029289528
Time median: 12.544539234000013
Time stddev: 0.08923337872052745
Time median: 12.498794928999928
Time stddev: 0.034226910872357456
Time median: 12.490837247500053
Time stddev: 0.06656521109199322
Time median: 12.452233578000005
Time stddev: 0.059151548542807124

Time minimum, all runs including warmups: 12.349883046999821
Avg median: 12.49298887
Spread: (max median - min median) / avg median = 0.007388596673

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
