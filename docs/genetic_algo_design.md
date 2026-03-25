# Genetic Algorithm Design

## Overview
The DoomSat payload uses a 2-Agent Micro-Population Steady-State Elitist Genetic Algorithm (µGA) to evolve behavioral parameters for the execution algorithm. This minimal-population approach is designed for:
- Low computational overhead (suitable for spacecraft constraints)
- Guaranteed non-regression (elite always preserved)
- Continuous adaptation through head-to-head competition


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


## Hyperparameters
| Hyperparameter | Value | Description |
|----------------|-------|-------------|
| Population size | 2 | Elite + challenger only |
| Radiation intensity | 0.25 | Represents probability per parameter of a bit-flip occuring (mutation) |
| Sigma (mutation std) | 15% of range | Per-parameter, adaptive |
| Generations | 50-1000 (Estimate) | Adjust based on convergence/time constraints |
| Episode timeout | 4200 tics (120 seconds) | E1M1 time limit |
| Evaluation seed | Fixed(42) | Same seed for all evaluations for fairness |


## Evolvable Parameters (keeping their ranges wide for observation)
**Exploration Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `loot_node_distance` | 200-800 units | Distance from agent that loot nodes are placed |

**Combat Parameters:**
None Currently

**Recovery Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `health_threshold` | 0-100 | Health level triggering RECOVER state |
| `armor_threshold` | 0-100 | Armor level triggering RECOVER state |
| `ammo_threshold` | 0-200 | Ammo level triggering RECOVER state |

**Scan Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `scan_frequency` | 0.0-1.0 | Probability of triggering scan (0=never, 1=every ~175 tics (5 seconds)) |
| `scan_cooldown` | 35-280 tics (1-8 seconds) | Minimum time between scans |

**Total:** 7 parameters per genome


## Fitness Function
**Weighted combination** - rewards completion, speed, and player stats:
```python
if level_completed:
    fitness = 1000                          # Base completion bonus
            + 500 * (1 - time_tics / 4200)  # Speed bonus 
            + 2 * health_remaining          # Health
            + 1 * armor_remaining           # Armor   
            + 0.5 * ammo_remaining          # Ammo 
else:
    fitness = 0
            + 5 * enemies_killed            # Partial credit for progress
            + 10 * waypoints_reached        # Proximity to goal
```

**Rationale:**
- Completion heavily weighted (1000 pts) - primary objective
- Completion speed matters 
- Health more valuable than armor (2× weight)
- Ammo carryover encouraged for future levels
- Failed runs get partial credit to improve when levels aren't being completed


## Mutation Strategy
1. Sample new value uniformly at random from the parameter's full valid range (simulating unpredictable bit-flip behavior)
2. Clamp mutated value to valid range to prevent invalid parameters


## Evolution Process
**Initialization (generation 0):**
1. Generate random Agent A within parameter ranges
2. Mutate A to create Agent B
3. Evaluate both on E1M1
4. Winner becomes initial elite

**Evolution:**
1. Agent B = mutate(Agent A)
2. Evaluate A and B on E1M1
3. Compare fitness scores
4. If fitness(B) > fitness(A):
       Agent A ← Agent B  (new elite)
   Else:
       Retain Agent A (elite preserved)
5. Save generation results
6. Repeat

**Termination:** Run for fixed number of generations.

## Evaluation Protocol
**Per-Agent Evaluation:**
- Map: E1M1
- Timeout: 4200 tics (120 seconds)
- Seed: Fixed (42) for reproducibility
- Mode: Fast (headless, action_frame_skip=8)

**Takes about 2 seconds per level**

**Metrics to collect:**
- Level completion status
- Episode time and tics
- Final health, armor, ammo
- Enemies killed
- Waypoints reached
- End reason (completion/death/timeout)


## Output & Logging
**During Evolution:**
- Console: Real-time progress (generation N, winner, fitness)

**After Evolution:**
- evolution_history.json: all generations, competitions, elite lineage
- final_elite.json: best genome parameters

## Post-Run Analysis
After evolution completes, generate plots from evolution_history.json:

**1. Fitness over Generations:**
- X-axis: Generation number
- Y-axis: Elite fitness
- Shows: Convergence trend

**2. Parameter Evolution:**
- X-axis: Generation number  
- Y-axis: Parameter value
- One line per parameter (8 lines total)
- Shows: Which params changed most

**3. Success Rate:**
- X-axis: Generation number (grouped by 5)
- Y-axis: % of elite wins vs challenger wins
- Shows: Elite stability over time


## Testing
- Verify fitness calculation (better performance = higher score)
- Test mutation produces valid parameters (all in range)
- Verify deterministic seeding (same seed = same result each run)
- Check parameters aren't stuck at min/max boundaries
- Re-evaluate final elite 3× to confirm consistency


## Future Work
- add GA param for aiming
- make the 2 genomes run in parallel (multithread)
- make visuals live using threading or web dashboard (Flask, Streamlit)
- plateau logic to determine when to stop evolving
- extend to E1M2
