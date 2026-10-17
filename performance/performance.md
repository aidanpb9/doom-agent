_place_node
wad lru
ga closing
telemetry file writes

## Regression
Determined that episodes have deterministic hashes.
Saved that result into performance/output/golden/
All new benchmarks test against this.

## Time
Restart PC.
Run an entire warmup benchmark.
Run alternating benchmark sessions for each commit, 3 each.
