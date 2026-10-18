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

## Episode benchmarks
Restarted pc and ran a warmup run, then alternated branches to get even benchmarks, 3 each.

Before avg median episode seconds: 12.53820346
Before avg stddev: 0.05424881443

After avg median episode seconds: 11.60218861
After avg stddev: 0.0919544081

Speedup: 12.54 / 11.60 = 1.08x speedup

## Parallel benchmarks
From running parallel_benchmark.py:

All results match across worker counts

Machine: 8 physical cores, 16 logical CPUs, 7620 MB memory
Tasks per generation: 10
Episode ticks: [2847, 2926, 3039, 3329, 3546, 3925, 6252, 7256, 10067, 12545]
Longest episode is 22.5% of all ticks, so no worker count can give more than 4.44x

workers  median s  stddev  speedup  effic  bound  avg CPU%  avg busy  peak RSS MB  min free MB
      1     63.40    0.14    1.00x   100%  1.00x         7       1.1          168         4969
      2     33.65    0.12    1.88x    94%  1.94x        13       2.1          257         4966
      4     18.34    0.06    3.46x    86%  3.62x        24       3.9          432         4909
      6     15.79    0.05    4.02x    67%  4.44x        31       5.0          604         4863
      8     16.82    0.17    3.77x    47%  4.44x        33       5.3          778         4833
     10     17.40    0.07    3.64x    36%  4.44x        36       5.7          954         4791
     12     17.40    0.05    3.64x    30%  4.44x        36       5.7         1085         4775

Using 6 workers gives a 4x speedup.
