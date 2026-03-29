# Genetic Algorithm Design

## Overview
The DoomSat payload uses a 2-Agent Micro-Population Steady-State Elitist Genetic Algorithm (µGA) to evolve behavioral parameters for the execution algorithm. This minimal-population approach is designed for low computational overhead which is suitable for spacecraft constraints. It also guarantees non-regression because the elite is always preserved. A crossover approach for mutating params is not used because the pool of genomes is not large enough, and this wouldn't reflect the radiation bit-flip anyways. The two agent will run in parallel, see docs/ga_parallelism.md.


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
| Eval runs | 5 | Episodes per genome per generation, averaged to reduce VizDoom RNG variance |
| Radiation intensity | 0.25 | Probability per parameter of a bit-flip mutation occurring |
| Sigma (mutation std) | 15% of range | Per-parameter, adaptive |
| Plateau generations | 10 | Generations without elite change before advancing to next level |
| Episode timeout | 12600 ticks (360 seconds) | E1M1 time limit |
| Evaluation seed | Random per episode | Python RNG seeded fresh each episode, seed recorded in Tier 1 Telemetry |


## Evolvable Parameters (keeping their ranges wide for observation)
**Exploration Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `loot_node_max_distance` | 200-1000 units | Distance from agent that loot nodes are placed |
| `stuck_recovery_ticks` | 35-140 ticks | Ticks of turn+forward to dislodge from obstacles |

**Combat Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `combat_hold_ticks` | 5-50 ticks | Ticks that agent stays in combat when enemy leaves FOV |

**Recovery Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `health_threshold` | 0-100 | Health level triggering RECOVER state |
| `armor_threshold` | 0-100 | Armor level triggering RECOVER state |
| `ammo_threshold` | 0-200 | Ammo level triggering RECOVER state |

**Scan Parameters:**
| Parameter | Range | Description |
|-----------|-------|-------------|
| `scan_interval` | 70-420 ticks (2-12sec) | How often agent is likely to scan |

**Total:** 7 parameters per genome


## Fitness Function
**Weighted combination** - rewards completion, speed, and player stats:
```python
if level_completed:
    fitness = 1000                          # Base completion bonus
            + 500 * (1 - time_ticks / 4200)  # Speed bonus 
            + 2 * health_remaining          # Health
            + 1 * armor_remaining           # Armor   
            + 0.5 * ammo_remaining          # Ammo 
else:
    fitness = 0
            + 5 * enemies_killed            # Partial credit for progress
            + 10 * waypoints_reached        # Proximity to goal
```

**Rationale:**
- Completion heavily weighted (1000 pts). It's the primary objective.
- Completion speed matters.
- Health more valuable than armor (2× weight).
- Ammo carryover encouraged for future levels.
- Failed runs get partial credit to improve when levels aren't being completed.


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
2. Evaluate A and B in parallel, for EVAL_RUNS episodes each
3. Compare averaged fitness scores
4. If fitness(B) > fitness(A):
       Agent A ← Agent B  (new elite)
   Else:
       Retain Agent A (elite preserved)
5. Save generation results
6. Competition occurs until plateau reached, then move onto next level

**Termination:** Plateau detection. Move on to next level if the level has been beaten and no elite change in PLATEAU_GENS generations. A single completion across any run in the generation is sufficient to set `level_beaten`. This is evidence of real capability given the multi-run averaging and stability requirement.

### Evolution Loop Diagram
Core evolution cycle from initialization through level advancement. Green = start/end, navy = actions, orange = decisions, teal = parallel evaluation, purple = level advancement.

```mermaid
flowchart TD
    classDef terminal fill:#2d6a4f,color:#fff,stroke:#1b4332
    classDef action   fill:#1d3557,color:#fff,stroke:#0d1b2a
    classDef decision fill:#e07b39,color:#fff,stroke:#b5541a
    classDef parallel fill:#0077b6,color:#fff,stroke:#023e8a
    classDef advance  fill:#6a0dad,color:#fff,stroke:#4a0080

    START([Start]):::terminal
    INIT[Generate random elite genome]:::action
    MUTATE[Mutate elite to challenger]:::action
    EVAL["Evaluate elite and challenger in parallel for EVAL_RUNS each"]:::parallel
    CMP{Challenger fitness > Elite?}:::decision
    SWAP[Challenger becomes new elite]:::action
    KEEP[Retain elite]:::action
    PLATEAU{Plateau reached?}:::decision
    NEXT[Advance to next level]:::advance
    DONE([Evolution complete]):::terminal

    START --> INIT --> MUTATE
    MUTATE --> EVAL --> CMP
    CMP -->|Yes| SWAP --> PLATEAU
    CMP -->|No| KEEP --> PLATEAU
    PLATEAU -->|No| MUTATE
    PLATEAU -->|Yes - more levels| NEXT --> MUTATE
    PLATEAU -->|Yes - all levels done| DONE
```

## Evaluation Protocol
**Per-Agent Evaluation:**
- Map: E1M1 until plateau, then E1M2 and so on
- Seed: A fresh random seed is generated and set at the start of each episode (`random.seed(seed)`). The seed is recorded in Tier 1. It controls Python RNG only (SCAN timing, STUCK turn direction), but VizDoom's internal RNG is independent and uncontrolled. This is the primary source of run-to-run variance. EVAL_RUNS episodes are averaged per genome to smooth this.

**Takes about 10 seconds per headless episode. So with 5 runs per genome running in parallel, a generation can take up to a minute.**

**Metrics to collect:**
- Level completion status
- Episode time and ticks
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
- One line per parameter (7 lines total)
- Shows: Which params changed most

**3. Success Rate:**
- X-axis: Generation number (grouped by 5)
- Y-axis: % of elite wins vs challenger wins
- Shows: Elite stability over time


## Testing
- Verify fitness calculation (better performance = higher score)
- Try to have agent converge on E1M1
- Test mutation produces valid parameters (all in range)
- Check parameters aren't stuck at min/max boundaries
- Re-evaluate final elite several times to confirm consistency


## Future Work
- make visuals