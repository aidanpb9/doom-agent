"""Micro-benchmark the improvements to adding lru_cache to utils.load_blocking_segments_from_wad.
To test this, the function in utils should not use lru_cache because it is added here.
The speedup is 150x, but the function is only called once per episodes, so the speedup is minimal."""

import sys
import timeit
from functools import lru_cache
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.utils import load_blocking_segments_from_wad
from config.constants import DEFAULT_WAD_PATH, DEFAULT_MAP_NAME

UNCACHED_FN = load_blocking_segments_from_wad
CACHED_FN = lru_cache(maxsize=64)(load_blocking_segments_from_wad)

# For timeit.repeat to share the same params for both functions.
REPEAT = 5
NUMBER = 200

def check_results_equal():
    """Checks that each function gives the same results,
    and that results from both functions are equal."""
    results = set()
    for _ in range(5):
        uncached_results = UNCACHED_FN(DEFAULT_WAD_PATH, DEFAULT_MAP_NAME)
        results.add(uncached_results)

        cached_results = CACHED_FN(DEFAULT_WAD_PATH, DEFAULT_MAP_NAME)
        results.add(cached_results)

    if len(results) > 1:
        raise ValueError("Results do not match")
    print("All results match")


def get_uncached_times() -> list:
    """Use the uncached function to benchmark time."""
    times = timeit.repeat(
        stmt=lambda: UNCACHED_FN(DEFAULT_WAD_PATH, DEFAULT_MAP_NAME),
        repeat=REPEAT,
        number=NUMBER
    )
    for i in range(len(times)):
        times[i] = times[i] / NUMBER
    return times


def get_cleared_cache_times() -> list:
    """Use the cached function to benchmark time, but clear the cache
    before every call. Use number=1 so that the cache is cleared properly.
    This shows that clearing the cache gives similar results to using
    the uncached function."""
    times = timeit.repeat(
        stmt=lambda: CACHED_FN(DEFAULT_WAD_PATH, DEFAULT_MAP_NAME),
        setup=CACHED_FN.cache_clear,
        repeat=REPEAT,
        number=1
    )
    return times


def get_cached_times() -> list:
    """Use the uncached function to benchmark time."""
    times = timeit.repeat(
        stmt=lambda: CACHED_FN(DEFAULT_WAD_PATH, DEFAULT_MAP_NAME),
        setup=CACHED_FN.cache_clear,
        repeat=REPEAT,
        number=NUMBER
    )
    for i in range(len(times)):
        times[i] = times[i] / NUMBER
    return times

if __name__ == "__main__":
    check_results_equal()

    uncached_times = get_uncached_times()
    uncached_avg = sum(uncached_times) / len(uncached_times)
    print(f"\nUncached times: {uncached_times}")
    print(f"avg: {uncached_avg}")

    cleared_times = get_cleared_cache_times()
    cleared_avg = sum(cleared_times) / len(cleared_times)
    print(f"\nCleared cache times: {cleared_times}")
    print(f"avg: {cleared_avg}")

    cached_times = get_cached_times()
    cached_avg = sum(cached_times) / len(cached_times)
    print(f"\nCached times: {cached_times}")
    print(f"avg: {cached_avg}")

    speedup = uncached_avg / cached_avg
    print(f"\nSpeedup: {speedup}\n")
