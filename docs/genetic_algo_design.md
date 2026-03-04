# Genetic Algorithm Design

## Overview

The DoomSat payload uses a 2-Agent Micro-Population Steady-State Elitist Genetic Algorithm (µGA) to evolve behavioral parameters for the execution algorithm. This minimal-population approach is designed for:
- Low computational overhead (suitable for spacecraft constraints)
- Guaranteed non-regression (elite always preserved)
- Continuous adaptation through head-to-head competition

**Goal:** Evolve parameters that maximize E1M1 completion rate and efficiency.

---

## Population Structure

**Population Size:** Exactly 2 agents

| Agent | Role | Mutation | Selection |
|-------|------|----------|-----------|
| **Agent A (Elite)** | Current best parameter set | No | Preserved unless defeated |
| **Agent B (Challenger)** | Mutated derivative of elite | Yes | Only promoted if superior |

**Steady-State Evolution:**
- Only one agent (challenger) changes per generation
- Elite is never discarded unless beaten
- Winner becomes new elite for next generation

---

## Evolvable Parameters (keeping their ranges wide for observation)

### Combat Parameters
| Parameter | Range | Description |
|-----------|-------|-------------|
| `strafe_switch_time` | 5-50 frames | Ticks before changing strafe direction during combat |

### Recovery Parameters
| Parameter | Range | Description |
|-----------|-------|-------------|
| `health_threshold` | 0-100 | Health level triggering RECOVER state |
| `armor_threshold` | 0-100 | Armor level triggering RECOVER state |
| `ammo_threshold` | 0-40 | Ammo level triggering RECOVER state |

### Scanning Parameters
| Parameter | Range | Description |
|-----------|-------|-------------|
| `scan_frequency` | 0.0-1.0 | Probability of triggering scan (0=never, 1.0=every ~10s) |
| `scan_cooldown` | 1.0-8.0 seconds | Minimum time between scans |

### Navigation Parameters
| Parameter | Range | Description |
|-----------|-------|-------------|
| `stuck_distance_threshold` | 64-150 units | Distance moved to avoid stuck detection |
| `stuck_time_threshold` | 3-7 seconds | Time before declaring stuck |

**Total:** 8 parameters per genome

---

## Fitness Function

**Weighted combination** - rewards completion, speed, and resource preservation:

```python
if level_completed:
    fitness = 1000                          # Base completion bonus
            + 1000 / time_seconds           # Speed bonus (faster = better)
            + 2 * health_remaining          # Health
            + 1 * armor_remaining           # Armor   
            + 0.5 * ammo_remaining          # Ammo 
else:
    fitness = 0
            + 5 * enemies_killed            # Partial credit for progress
            + 20 * waypoints_reached        # Proximity to goal
```

**Rationale:**
- Completion heavily weighted (1000 pts) - primary objective
- Speed matters (up to 600 pts for 0s vs 60s)
- Health more valuable than armor (2× weight)
- Ammo carryover encouraged for future levels
- Failed runs get partial credit to improve when levels aren't being completed


## Mutation Strategy

**Gaussian perturbation** applied independently to each parameter:

1. For each parameter, with 25% probability:
   - Add random noise sampled from Gaussian distribution
   - Mean = 0 (centered on current value)
   - Standard deviation = 15% of parameter's valid range
   
2. Clamp mutated value to valid range to prevent invalid parameters

**Example:**
- Elite has `health_threshold = 50`
- Parameter range is [0, 100], range size = 100
- Sigma = 15% of range = 15
- Mutation samples from N(50, 15²)
- Mutated value clamped to [0, 100]

**Rationale:**
- 25% mutation rate and 15% sigma balances exploration vs exploitation
- Also mutations are based on their range, so smaller ranges get smaller mutations


## Evolution Process

### Initialization (Generation 0)
```
1. Generate random Agent A within parameter ranges
2. Mutate A to create Agent B
3. Evaluate both on E1M1
4. Winner becomes initial elite
```

### Per Generation (N ≥ 1)
```
1. Agent B = mutate(Agent A)
2. Evaluate A and B on E1M1
3. Compare fitness scores
4. If fitness(B) > fitness(A):
       Agent A ← Agent B  (new elite)
   Else:
       Retain Agent A (elite preserved)
5. Save generation results
6. Repeat
```

**Termination:** Run for fixed number of generations or until success rate plateau.

---

## Evaluation Protocol

**Per-Agent Evaluation:**
- Map: E1M1
- Timeout: 120 seconds
- Seed: Deterministic based on `hash(genome_params)` for reproducibility
- Mode: Fast (headless, action_frame_skip=8)


**Metrics Collected:**
- Level completion status
- Episode time
- Final health, armor, ammo
- Enemies killed
- Waypoints reached (if failed)
- End reason (exit/death/timeout)


## Elite Preservation & Lineage

**Elitism Guarantee:**
- Elite genome never replaced unless challenger strictly better
- Ties favor elite (no change)

**Lineage Tracking:**
```python
{
    'generation': int,
    'agent_id': 'A' or 'B',
    'parent_id': str,  # Previous elite
    'fitness': float,
    'parameters': {...}
}
```

Enables:
- Evolutionary history analysis
- Parameter trend visualization
- Rollback to previous elite if needed

---

## Output & Logging

**Per Generation:**
- `generation_NNN.json` - Competition results, both genomes, winner
- Console log - Parameter changes, fitness scores, winner announcement

**Cumulative:**
- `evolution_history.json` - All competitions, elite lineage, best fitness
- `final_elite.json` - Best genome found

**Visualization (post-processing):**
- Fitness over generations
- Parameter evolution trajectories
- Success rate trends

---

## Hyperparameters (Fixed, Not Evolved)

| Hyperparameter | Value | Description |
|----------------|-------|-------------|
| Population size | 2 | Elite + challenger only |
| Mutation rate | 0.25 | 25% chance per parameter |
| Sigma (mutation std) | 10-20% of range | Per-parameter, adaptive |
| Generations | 20-50 | Or until plateau |
| Episode timeout | 120s | E1M1 time limit |
| Evaluation seed | `hash(genome)` | Deterministic per genome |

---

## Expected Performance

**Baseline (random parameters):**
- Success rate: 20-40%
- Average time: 45-60s (when successful)

**After 20 generations:**
- Success rate: 60-80% (target)
- Average time: 30-45s
- Health preserved: 60+ avg

**Convergence indicators:**
- Plateau in fitness improvement (3+ gens with no elite change)
- Success rate stabilizes
- Parameter values oscillate in narrow range

---

## Future Extensions

**Multi-Level Evolution (E1M1 → E1M2):**
- Fitness = average across multiple levels
- Encourages generalization over specialization

**Adaptive Mutation Rate:**
- Decrease sigma as fitness improves (simulated annealing)
- Prevents disrupting good solutions

**Multi-Objective Optimization:**
- Pareto front: completion vs speed vs damage
- Select diverse strategies

**Spacecraft Integration:**
- Radiation-induced mutations (real bit flips)
- Telemetry-based fitness evaluation
- Memory-mapped parameter storage

---

## Testing & Validation

**Before Evolution:**
1. Verify fitness function gives expected ordering
2. Test mutation produces valid parameters (all in range)
3. Confirm evaluation runs without crashes
4. Check deterministic seeding works (same seed = same result)

**During Evolution:**
1. Monitor for fitness regression (should never happen with elitism)
2. Check parameter diversity (not stuck at boundaries)
3. Verify logging/saving works each generation

**After Evolution:**
1. Re-evaluate final elite 10× times to confirm robustness
2. Compare to hand-tuned baseline
3. Test on unseen seed values

---

## Success Criteria

**Minimal Success (Sprint Goal):**
- Elite beats E1M1 with >60% success rate
- Improvement over random baseline demonstrable
- GA runs without crashes for 20 generations

**Target Success:**
- Elite beats E1M1 with >80% success rate
- Avg completion time <40 seconds
- Clear fitness improvement curve visible

**Stretch Success:**
- Elite generalizes to E1M2 (>50% success without retraining)
- Parameter insights documented (which matter most)
- Comparison with NN baseline (if time permits)