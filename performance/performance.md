## Optimizations To Do
_place_node
ga closing
telemetry file writes

## Benchmark Process
Restart PC.
Run an entire warmup benchmark.

## Regression
Determined that episodes have deterministic hashes.
Saved that result into performance/output/golden/
All new benchmarks test against this.

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
