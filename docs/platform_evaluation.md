# Platform Evaluation: VizDoom vs Emulator

**Task:** User Story 2.A - Evaluate VizDoom capabilities for full Doom 1 (E1M1-E3M9)  
**Date:** February 10, 2026  
**Team:** Doom Team

## Task Overview

Research and document whether VizDoom can run full Doom 1 or only FreeDoom scenarios.

**Ready Criteria:**
- VizDoom installed and basic scenario tested
- Doom 1 IWAD file available

**Acceptance Criteria:**
- VizDoom supported scenarios documented
- Limitations or constraints clearly stated


## VizDoom Capabilities

### Supported Content

VizDoom successfully runs full Doom 1 (registered version) with all episodes and levels.

**WAD Verification:**

Tested `doom.wad` compatibility with all episodes:

- Episode 1: E1M1-E1M9 ✓
- Episode 2: E2M1-E2M9 ✓  
- Episode 3: E3M1-E3M9 ✓

**Total: 27 levels confirmed working**

Command:
- run this code block, it shows all 27 levels opening
- make sure doom.wad is named correctly in the wads folder 
- YOU MUST VISUALLY VERIFY THAT DIFFERENT LEVELS ARE BEING OPENED

python3 -c "import vizdoom as vzd; import time; game = vzd.DoomGame(); game.set_doom_scenario_path('wads/doom.wad'); [print(f'✓ E{ep}M{lv}') if (game.set_doom_map(f'E{ep}M{lv}'), game.init(), time.sleep(0.5), game.close(), True)[-1] else print(f'✗ E{ep}M{lv}') for ep in [1,2,3] for lv in range(1,10)]"

**WAD File Details:**
- File: `doom.wad`
- Size: 10 MB
- Type: Registered Doom (Episodes 1-3)

## Limitations and Constraints

### VizDoom Platform Limitations

**Verified Issues:**
1. **Segmentation fault on exit:** VizDoom crashes during cleanup after successful episode completion. This is a known cosmetic issue that does not affect gameplay or results.


**Platform Constraints:**
1. **Action space:** Has many available actions, but not all are useful/necessary. View all actions with: 

    python3 -c "import vizdoom as vzd; [print(attr) for attr in dir(vzd.Button) if not attr.startswith('_')]"
2. **Seed:** Random. Seeds don't guarantee deterministic reproducibility. See ga design doc for more info
3. **Tick rate:** Affects how fast things happen in game. VizDoom's tick rate is 35 by default. We will not change this. 
3. **Testing Speed:** Slow/fast modes are controlled with frame skip. In fast mode the agent makes decisions about 4 times per second (sees every 8 frames). In slow mode it is 35 times per second. This means there will be some difference in behavior between the modes. So, the genetic algorithm will be ran in fast mode while slow mode will be used for demos, observations, and testing.

### CubeSat-Specific Constraints

**Operational Constraints:**
- Episodes must complete within timeout window
- Fast mode necessary for reasonable execution speed
- Limited to vanilla Doom content (no complex WAD mods)

## Alternative Evaluation (researched using Claude Sonnet 4.5)

### Native Doom Emulators Considered

**Chocolate Doom:**
- Pros: Exact vanilla Doom behavior, very low overhead, faithful reproduction
- Cons: No Python API, no reinforcement learning interface, would require custom wrapper development

**PrBoom+:**
- Pros: Enhanced Doom port with demo recording, good performance, widely used for speedrunning
- Cons: No built-in RL API, would require manual I/O parsing (demo files or memory reading), significant integration effort

**Crispy Doom:**
- Pros: Faithful to original with QoL improvements, lightweight, maintains vanilla limits
- Cons: No programmatic control interface, same integration challenges as Chocolate Doom

**Why VizDoom was chosen:**
- Native Python API for agent control
- Direct access to game state (position, health, enemies, etc.)
- Screen buffer and label support for perception
- Designed specifically for RL research
- Active development and community support
- Built on ZDoom engine (more features than vanilla while maintaining compatibility)

While native emulators offer faithful Doom execution, VizDoom's purpose-built RL interface eliminates months of wrapper development work. Despite minor limitations (exit crash, memory footprint), VizDoom's capabilities outweigh alternatives that would require custom integration layers.

## Conclusion

VizDoom is confirmed suitable for the DoomSat mission.
Platform limitations are manageable and do not block mission objectives.
While native emulators offer faithful Doom execution, VizDoom's purpose-built RL interface eliminates months of wrapper development work.