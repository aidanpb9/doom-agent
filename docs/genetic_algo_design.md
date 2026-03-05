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
| Mutation rate | 0.25 | 25% chance per parameter |
| Sigma (mutation std) | 15% of range | Per-parameter, adaptive |
| Generations | 50-1000 | Adjust based on convergence/time constraints |
| Episode timeout | 4200 tics (120 seconds) | E1M1 time limit |
| Evaluation seed | Fixed(42) | Same seed for all evaluations for fairness |


## Evolvable Parameters (keeping their ranges wide for observation)
**Exploration Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `anchor_frequency` | 0.0-0.1  | Probability per tic of dropping an anchor node (0=never, 0.1=10% chance per tic) |
| `loot_node_distance` | 200-800 units | Distance from agent that loot nodes are placed |


**Combat Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `strafe_switch_time` | 5-50 tics | Ticks before changing strafe direction during combat |

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

**Total:** 8 parameters per genome


## Fitness Function
**Weighted combination** - rewards completion, speed, and player stats:

```python
if level_completed:
    fitness = 1000                          # Base completion bonus
             500 * (1 - time_tics / 4200)   # Speed bonus 
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
- Completion speed matters 
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
- make the 2 genomes run in parallel (multithread)
- make visuals live using threading or web dashboard (Flask, Streamlit)
- extend to E1M2
